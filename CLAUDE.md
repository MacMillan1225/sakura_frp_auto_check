# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is an automated FRP (NATFRP) check-in bot built with Python and Playwright. The application automates daily sign-in on www.natfrp.com with CAPTCHA solving capabilities.

## Architecture

### Core Components

- **main.py**: Single-file application containing the entire automation logic
- **Computer Vision Module** (`get_gap_offset`): Uses OpenCV to solve sliding CAPTCHA puzzles by detecting gaps in background images
- **Browser Automation**: Uses Playwright to interact with the NATFRP website
- **State Management**: Preserves login sessions using `state.json` to avoid repeated logins
- **Retry Logic**: Built-in retry mechanism with configurable maximum attempts

### Key Functions

- `get_gap_offset()`: CAPTCHA solver using image difference detection in main.py:7-51
- `main()`: Main automation workflow in main.py:251-324
- `solve_geetest_puzzle()`: Handles GeeTest CAPTCHA solving in main.py:220-235
- `wait_signed_text_and_shoot()`: Success detection and screenshot capture in main.py:238-248

## Running the Application

### Basic Execution
```bash
python main.py
```

### Dependencies
The project requires:
- playwright
- opencv-python (cv2)
- pathlib (built-in)

Install Playwright browsers after installing the package:
```bash
playwright install chromium
```

## Configuration Files

- **account.txt**: Contains username (line 1) and password (line 2) for NATFRP login
- **state.json**: Browser session state for maintaining login sessions
- **.gitignore**: Excludes sensitive files and debug images

## Generated Files

- **bg.png, fullbg.png**: CAPTCHA background images extracted during solving
- **debug_*.png**: Debug images for CAPTCHA solving analysis (when debug=True)
- **checkin.png**: Screenshot saved upon successful sign-in

## Configuration Variables

Key settings in main.py:53-64:
- `MAX_RETRY`: Maximum retry attempts (0 for infinite)
- `ALREADY_SIGNED_TEXT`: Success detection text ("今天已经签到过啦")
- `SIGNED_ANCESTOR_LEVELS`: Screenshot capture depth (3 parent levels)
- `SIGNED_ANCESTOR_SCREENSHOT`: Success screenshot filename

## CAPTCHA Solving Process

1. Extract background image with gap (`bg.png`)
2. Extract complete background image (`fullbg.png`)
3. Calculate absolute difference between images
4. Apply binary threshold and find contours
5. Select gap location based on largest contours
6. Simulate human-like mouse dragging to solve

## Browser Configuration

- Runs in non-headless mode by default (`headless=False`)
- Uses `slow_mo=200` for human-like interaction timing
- Maintains session state between runs via `state.json`