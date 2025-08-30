from playwright.sync_api import sync_playwright
import os
import cv2
import numpy as np
import time
import random
import mycv

from pathlib import Path

# 目标地址
domain = "www.natfrp.com"
target_url = f"https://{domain}/user/"

# cookie 文件路径
COOKIE_FILE = Path("cookies.txt")

# 状态文件
STATE_FILE = "state.json"

def load_cookies_from_file(path: Path) -> str:
    """从文件读取 Cookie 字符串"""
    if not path.exists():
        raise FileNotFoundError(f"Cookie 文件不存在: {path}")
    return path.read_text(encoding="utf-8").strip()

def inject_initial_cookies(context):
    """将文本文件中的 cookies 注入 Context"""
    cookies_str = load_cookies_from_file(COOKIE_FILE)
    cookies_list = []
    # 按分号拆分为 name=value
    for pair in cookies_str.split(";"):
        pair = pair.strip()
        if not pair:
            continue
        if "=" not in pair:
            print(f"[WARN] 无效的 cookie 格式: {pair}")
            continue
        name, value = pair.split("=", 1)
        cookies_list.append({
            "name": name.strip(),
            "value": value.strip(),
            "domain": domain,
            "path": "/",
            "secure": True,
            "httpOnly": False
        })
    context.add_cookies(cookies_list)
    print("[INFO] 已注入初始 Cookie")

def confirm_age_if_needed(page):
    """等待并点击 '是，我已满18岁' 按钮"""
    try:
        print("[INFO] 尝试点击")
        page.wait_for_selector('text=是，我已满18岁', timeout=5000)
        page.click('text=是，我已满18岁')
        print("[INFO] 已点击满18岁确认按钮")
    except:
        print("[INFO] 没有检测到满18岁确认按钮，跳过")

def sign_in_if_needed(page):
    """等待并点击 '点击这里签到' 按钮"""
    try:
        page.wait_for_selector('text=点击这里签到', timeout=5000)
        page.click('text=点击这里签到')
        print("[INFO] 已点击签到按钮")
    except:
        print("[INFO] 没有检测到签到按钮，跳过")

def human_track(distance):
    """只有加速、匀速、减速三步轨迹"""
    track = []
    current = 0

    # 比例分配
    accel_dist = distance * 0.3
    const_dist = distance * 0
    decel_dist = distance - accel_dist - const_dist

    # 加速段（第1步）
    move = accel_dist + random.uniform(-2, 2)  # 加点随机
    current += move
    track.append(round(move))

    # 匀速段（第2步）
    move = const_dist + random.uniform(-2, 2)
    current += move
    track.append(round(move))

    # 减速段（第3步）
    move = decel_dist + random.uniform(-1, 1)
    # 修正最后一步到终点
    if current + move != distance:
        move = distance - current
    current += move
    track.append(round(move))

    return track


def solve_geetest_puzzle(page):
    # 等待拼图组件加载出来
    page.wait_for_selector('.geetest_slider_button', timeout=10000)

    # 截图有缺口背景
    bg_path = "bg.png"
    fullbg_path = "fullbg.png"
    page.query_selector('.geetest_canvas_bg').screenshot(path=bg_path)

    # 显示完整背景（fullbg）
    page.evaluate("""
        document.querySelector('.geetest_canvas_fullbg').style.display = 'block';
    """)
    page.query_selector('.geetest_canvas_fullbg').screenshot(path=fullbg_path)
    # 再隐藏回去
    page.evaluate("""
        document.querySelector('.geetest_canvas_fullbg').style.display = 'none';
    """)

    # 用 OpenCV 算缺口位置
    gap_x = mycv.get_gap_offset(bg_path, fullbg_path, debug=True)
    print(f"[INFO] 检测到缺口 x 坐标: {gap_x}")

    # 获取滑块位置
    slider = page.query_selector('.geetest_slider_button')
    box = slider.bounding_box()

    # 计算最终滑动距离（可加比例修正，这里先简单用缺口值）
    distance = gap_x - 6
    print(f"[INFO] 需要滑动距离: {distance}")

    track = human_track(distance)
    print("[INFO] 生成滑动轨迹:", track)

    # 计算起始位置
    start_x = box['x'] + box['width'] / 2
    start_y = box['y'] + box['height'] / 2

    # 模拟人类轨迹
    current_x = start_x
    current_y = start_y

    page.mouse.move(start_x, start_y)
    page.mouse.down()

    for move in track:
        current_x += move
        page.mouse.move(current_x, current_y, steps=50)
    page.mouse.up()

    print("[INFO] 拼图滑动完成")

def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=200)

        try:
            context = browser.new_context(storage_state=STATE_FILE)
            print("[INFO] 使用保存的登录状态")
        except Exception as e:
            print(f"[WARN] 读取登录状态失败: {e}")
            context = browser.new_context()
            try:
                inject_initial_cookies(context)
            except Exception as e2:
                print(f"[WARN] 注入 Cookie 文件失败: {e2}")
                # 在这里可以提示用户输入 Cookie 字符串

        print("[INFO] aaaaaa")
        page = context.new_page()
        page.goto(target_url, wait_until="domcontentloaded")

        # 满 18 岁确认
        confirm_age_if_needed(page)

        # 签到
        sign_in_if_needed(page)

        # 处理验证码
        solve_geetest_puzzle(page)

        # 保存登录状态
        context.storage_state(path=STATE_FILE)
        print(f"[INFO] 登录状态已保存到 {STATE_FILE}")

        page.wait_for_timeout(5000)
        browser.close()

if __name__ == "__main__":
    main()