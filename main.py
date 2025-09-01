from playwright.sync_api import sync_playwright
from pathlib import Path
import random
import mycv
import time

# ========= 配置 =========
domain = "www.natfrp.com"
target_url = f"https://{domain}/user/"
ACCOUNT_FILE = Path("account.txt")  # 第一行用户名，第二行密码
STATE_FILE = "state.json"
MAX_RETRY = 5  # 0 表示无限重试，>0 表示最大重试次数
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

    gap_x = mycv.get_gap_offset(bg_path, fullbg_path, debug=True)
    print(f"[INFO] 缺口坐标: {gap_x}")

    slider = page.query_selector('.geetest_slider_button')
    distance = gap_x

    drag_slider_fixed_steps(page, slider, distance, button_type="left", debug_pause=False)
    print("[INFO] 验证码滑动完成")

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

        confirm_age_if_needed(page)

        # 检查状态文件里的 cookie 是否失效
        if is_cookie_expired(page):
            print("[WARN] Cookie 已过期，使用账号密码登录")
            login_with_user_pass(page, username, password)
            if is_logged_in(page):
                print("[INFO] 登录成功，更新状态文件")
                context.storage_state(path=STATE_FILE)
            else:
                print("[ERROR] 登录失败")
                browser.close()
                return False

        if is_sign_button_visible(page):
            click_sign_in_button(page)
            if is_captcha_visible(page):
                solve_geetest_puzzle(page)
                if wait_captcha_disappear(page):
                    print("[INFO] 签到成功（验证码消失）")
                    browser.close()
                    return True
                else:
                    print("[ERROR] 签到失败，验证码未消失")
                    browser.close()
                    return False
            else:
                print("[INFO] 无需验证码，签到成功")
                browser.close()
                return True
        else:
            print("[INFO] 未发现签到按钮，可能已签到")
            browser.close()
            return True

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