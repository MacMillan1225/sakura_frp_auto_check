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

if __name__ == "__main__":
    # 测试
    bg_path = "bg.png"          # 有缺口背景
    fullbg_path = "fullbg.png"  # 完整背景
    gap_offset = get_gap_offset(bg_path, fullbg_path, debug=True)
    print(f"缺口位置 x 坐标: {gap_offset}")