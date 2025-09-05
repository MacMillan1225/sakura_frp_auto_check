from playwright.sync_api import sync_playwright
from pathlib import Path
import random
import time
import cv2

def get_gap_offset(bg_path, fullbg_path, debug=False):
    """比较有缺口背景图和完整背景图，找到缺口 x 坐标（取前两个最大轮廓，选x更大者）"""
    # 1. 灰度读取
    bg_img = cv2.imread(bg_path, 0)
    fullbg_img = cv2.imread(fullbg_path, 0)
    if debug:
        cv2.imwrite("debug_01_bg_gray.png", bg_img)
        cv2.imwrite("debug_02_fullbg_gray.png", fullbg_img)

    # 2. 计算绝对差
    diff = cv2.absdiff(fullbg_img, bg_img)
    if debug:
        cv2.imwrite("debug_03_diff.png", diff)

    # 3. 二值化
    _, thresh = cv2.threshold(diff, 25, 255, cv2.THRESH_BINARY)
    if debug:
        cv2.imwrite("debug_04_thresh.png", thresh)

    # 4. 找轮廓
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    if len(contours) < 2:
        raise ValueError("[ERROR] 找到的轮廓少于两个，可能识别失败")

    # 5. 按面积排序，取前两个最大的
    contours_sorted = sorted(contours, key=cv2.contourArea, reverse=True)[:2]

    # 6. 获取它们的 bounding box
    rects = [cv2.boundingRect(c) for c in contours_sorted]

    # 7. 选择 x 坐标更大的那个
    target_rect = max(rects, key=lambda r: r[0])
    x, y, w, h = target_rect

    # 8. 调试输出
    if debug:
        debug_img = cv2.cvtColor(bg_img, cv2.COLOR_GRAY2BGR)
        for rect in rects:
            cx, cy, cw, ch = rect
            cv2.rectangle(debug_img, (cx, cy), (cx+cw, cy+ch), (0,255,0), 2)
        cv2.rectangle(debug_img, (x, y), (x+w, y+h), (0,0,255), 2)
        cv2.imwrite("debug_05_with_box.png", debug_img)

    return x

# ========= 配置 =========
domain = "www.natfrp.com"
target_url = f"https://{domain}/user/"
ACCOUNT_FILE = Path("account.txt")  # 第一行用户名，第二行密码
STATE_FILE = "state.json"
MAX_RETRY = 5  # 0 表示无限重试，>0 表示最大重试次数

# --- 新增/修改 ---
ALREADY_SIGNED_TEXT = "今天已经签到过啦"       # 用于判定成功的文案（包含即可）
SIGNED_ANCESTOR_LEVELS = 3                 # 向上取第 3 层父级
SIGNED_ANCESTOR_SCREENSHOT = "checkin.png"  # 成功时保存截图的文件名
# ========================

# ---------------- 读取账号密码 ----------------
def load_username_password(path: Path):
    if not path.exists():
        raise FileNotFoundError(f"{path} 文件不存在")
    lines = [l.strip() for l in path.read_text(encoding="utf-8").strip().splitlines() if l.strip()]
    if len(lines) < 2:
        raise ValueError("account.txt 必须至少有两行：用户名、密码")
    return lines[0], lines[1]

# ---------------- 检测函数 ----------------
def is_cookie_expired(page, timeout=6000):
    try:
        # 页面出现“Nyatwork 登录”说明需要重新登录
        page.wait_for_selector("text=Nyatwork 登录", timeout=timeout)
        return True
    except:
        return False

def confirm_age_if_needed(page, timeout=6000):
    try:
        page.wait_for_selector('text=是，我已满18岁', timeout=timeout)
        page.click('text=是，我已满18岁')
        print("[INFO] 已点击满18岁确认按钮")
    except:
        print("[INFO] 无需进行年龄确认")

def is_logged_in(page, timeout=6000):
    try:
        page.wait_for_selector("text=账号信息", timeout=timeout)
        print("[INFO] 检测到已登录状态")
        return True
    except:
        return False

def is_sign_button_visible(page, timeout=6000):
    try:
        page.wait_for_selector("text=点击这里签到", timeout=timeout)
        return True
    except:
        return False

def is_captcha_visible(page, timeout=6000):
    try:
        page.wait_for_selector(".geetest_slider_button", timeout=timeout)
        return True
    except:
        return False

def wait_captcha_disappear(page, timeout=10000):
    try:
        page.wait_for_selector("text=签到成功", timeout=timeout)
        return True
    except:
        return False

# --- 新增/修改：查找“今天已经签到过啦”的元素（包含匹配），并取其第 N 层父级 ---
def find_signed_text_locator(page, timeout=6000):
    """
    返回包含“今天已经签到过啦”的元素 locator（取第一个可见）。
    使用 normalize-space 规避前后空格影响，并做“包含”匹配。
    """
    selector = "text=%s" % ALREADY_SIGNED_TEXT
    try:
        page.wait_for_selector(selector, timeout=timeout)
        return page.locator(selector).first
    except Exception as e:
        return None

def screenshot_signed_text_ancestor(page, levels: int = SIGNED_ANCESTOR_LEVELS,
                                    path: str = SIGNED_ANCESTOR_SCREENSHOT,
                                    timeout: int = 6000) -> bool:
    """
    截图“包含『今天已经签到过啦』的元素”的第 levels 层父级。
    若未找到该元素或父级，兜底整页截图。返回 True 表示截到了祖先元素，False 表示做了兜底。
    """
    base = find_signed_text_locator(page, timeout=timeout)
    if base is None:
        # 没找到文本元素，整页兜底
        try:
            page.screenshot(path=path, full_page=True)
            print(f"[WARN] 未找到包含『{ALREADY_SIGNED_TEXT}』的元素，已兜底整页截图：{path}")
        except Exception as e:
            print(f"[ERROR] 兜底整页截图失败：{e}")
            return False
        return False

    try:
        # 取第 N 层父级
        ancestor = base.locator(f"xpath=ancestor::*[{levels}]").first
        # 有些页面结构不够深，尝试逐级回退
        for lvl in range(levels, 0, -1):
            candidate = base.locator(f"xpath=ancestor::*[{lvl}]").first
            try:
                candidate.wait_for(state="visible", timeout=1200)
                try:
                    candidate.scroll_into_view_if_needed()
                except:
                    pass
                candidate.screenshot(path=path)
                print(f"[INFO] 已保存签到截图：{path}")
                return True
            except:
                continue

        # 如果所有层级都没成功，整页兜底
        page.screenshot(path=path, full_page=True)
        print(f"[WARN] 祖先节点截图未成功，已兜底整页截图：{path}")
        return False
    except Exception as e:
        print(f"[ERROR] 祖先截图异常：{e}")
        try:
            page.screenshot(path=path, full_page=True)
            print(f"[WARN] 异常时已兜底整页截图：{path}")
        except:
            return False
        return False

# ---------------- 操作函数 ----------------
def login_with_user_pass(page, username, password):
    page.fill("#username", username)
    page.fill("#password", password)
    page.click("button[id=login]")
    print("[INFO] 已提交登录表单")

def click_sign_in_button(page):
    page.click("text=点击这里签到")
    print("[INFO] 已点击签到按钮")

def drag_slider_fixed_steps(page, slider_element, distance, button_type="middle", debug_pause=False):
    box = slider_element.bounding_box()
    start_x = int(box['x'])
    start_y = int(box['y'] + box['height'] / 2)

    print(f"[INFO] 滑块初始坐标: ({start_x}, {start_y})")
    print(f"[INFO] 目标滑动距离: {distance} 像素")

    page.mouse.move(start_x, start_y)
    page.mouse.down(button=button_type)
    page.wait_for_timeout(300)

    page.mouse.move(start_x + distance + random.randint(2, 8), start_y)
    page.wait_for_timeout(500)

    page.mouse.move(start_x + distance - 2, start_y)
    page.mouse.move(start_x + distance - 6, start_y)
    page.wait_for_timeout(400)
    page.mouse.move(start_x + distance - 8, start_y)

    page.mouse.up(button=button_type)
    print("[INFO] 滑动完成")

    if debug_pause:
        page.pause()

def solve_geetest_puzzle(page):
    bg_path = "bg.png"
    fullbg_path = "fullbg.png"
    page.query_selector('.geetest_canvas_bg').screenshot(path=bg_path)
    page.evaluate("""document.querySelector('.geetest_canvas_fullbg').style.display = 'block';""")
    page.query_selector('.geetest_canvas_fullbg').screenshot(path=fullbg_path)
    page.evaluate("""document.querySelector('.geetest_canvas_fullbg').style.display = 'none';""")

    gap_x = get_gap_offset(bg_path, fullbg_path, debug=True)
    print(f"[INFO] 缺口坐标: {gap_x}")

    slider = page.query_selector('.geetest_slider_button')
    distance = gap_x

    drag_slider_fixed_steps(page, slider, distance, button_type="left", debug_pause=False)
    print("[INFO] 验证码滑动完成")

# --- 新增/修改：以“今天已经签到过啦”判定成功 ---
def wait_signed_text_and_shoot(page, timeout=8000) -> bool:
    """
    等待出现包含『今天已经签到过啦』的元素；出现则截图其第 3 层父级并返回 True。
    若未出现则返回 False。
    """
    loc = find_signed_text_locator(page, timeout=timeout)
    if loc is None:
        return False
    # 找到了就截图祖先
    screenshot_signed_text_ancestor(page, SIGNED_ANCESTOR_LEVELS, SIGNED_ANCESTOR_SCREENSHOT)
    return True

# ---------------- 主逻辑 ----------------
def main() -> bool:
    """
    主流程
    :return: True 表示成功，False 表示失败需要重试
    """
    username, password = load_username_password(ACCOUNT_FILE)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=200)

        # 先尝试从 state.json 加载状态（cookie/session）
        try:
            context = browser.new_context(storage_state=STATE_FILE)
            print("[INFO] 已加载保存的状态文件")
        except:
            print("[WARN] 未找到状态文件，将新建上下文")
            context = browser.new_context()

        page = context.new_page()
        page.goto(target_url, timeout=8000)

        # 登录后再检查 18 岁确认（若页面已处于登录态也会直接检测）
        if is_logged_in(page):
            confirm_age_if_needed(page)
        else:
            # 检查状态文件里的 cookie 是否失效
            if is_cookie_expired(page):
                print("[WARN] Cookie 已过期，使用账号密码登录")
                login_with_user_pass(page, username, password)
                if is_logged_in(page):
                    print("[INFO] 登录成功，更新状态文件")
                    context.storage_state(path=STATE_FILE)
                    # 登录成功后再检查一次 18 岁确认
                    confirm_age_if_needed(page)
                else:
                    print("[ERROR] 登录失败")
                    browser.close()
                    return False

        # --- 新增/修改：页面若已出现“今天已经签到过啦”，直接判定成功并截图祖先 ---
        if wait_signed_text_and_shoot(page, timeout=2000):
            print("[INFO] 已经签到过啦（页面已有提示）")
            browser.close()
            return True

        # 正常签到流程
        if is_sign_button_visible(page):
            click_sign_in_button(page)
            if is_captcha_visible(page):
                solve_geetest_puzzle(page)
                # 成功判定：等待出现“今天已经签到过啦”
                if wait_signed_text_and_shoot(page, timeout=10000):
                    print("[INFO] 签到成功（出现『今天已经签到过啦』）")
                    browser.close()
                    return True
                else:
                    print("[ERROR] 签到失败：未出现『今天已经签到过啦』提示")
                    browser.close()
                    return False
            else:
                # 无验证码路径：同样等待出现成功提示
                if wait_signed_text_and_shoot(page, timeout=8000):
                    print("[INFO] 签到成功（无需验证码）")
                    browser.close()
                    return True
                else:
                    print("[ERROR] 签到失败：未出现『今天已经签到过啦』提示（无需验证码路径）")
                    browser.close()
                    return False
        else:
            # 不再以“找不到按钮”作为成功判据；此分支仅作为提示与失败返回
            print("[ERROR] 未发现签到按钮，且未检测到『今天已经签到过啦』提示")
            browser.close()
            return False

# ---------------- 带重试启动 ----------------
if __name__ == "__main__":
    attempt = 0
    while True:
        attempt += 1
        print(f"[INFO] 第 {attempt} 次执行签到")
        try:
            success = main()
        except Exception as e:
            print(f"[ERROR] 程序异常: {e}")
            success = False

        if success:
            print("[INFO] 本次执行成功，退出程序")
            break
        else:
            if MAX_RETRY > 0 and attempt >= MAX_RETRY:
                print("[ERROR] 超过最大重试次数，退出程序")
                break
            print("[WARN] 本次失败，10秒后重试")
            time.sleep(10)
