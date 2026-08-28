"""icons/og-image.png(카카오톡/소셜 공유 미리보기용, 1200x630)을 만드는 스크립트.
전국 GPS 기반으로 바뀐 뒤에도 이미지 안에 "부천 사는 아빠가 만든"이라는 예전 문구가
그대로 박혀있던 걸 뒤늦게 발견해서(2026-08-28, 이력서용으로 쓰려는데 안 맞는다는
피드백) 다시 만든다. 매번 다시 실행할 일은 거의 없어서 파이프라인에는 안 넣고
필요할 때 수동으로 돌린다.
"""
from PIL import Image, ImageDraw, ImageFont

OUTPUT_PATH = "icons/og-image.png"
SIZE = (1200, 630)
FONT_BOLD = "C:/Windows/Fonts/malgunbd.ttf"
FONT_REGULAR = "C:/Windows/Fonts/malgun.ttf"


def build_gradient(size, top_color, bottom_color):
    w, h = size
    img = Image.new("RGB", size, top_color)
    draw = ImageDraw.Draw(img)
    for y in range(h):
        t = y / (h - 1)
        r = round(top_color[0] + (bottom_color[0] - top_color[0]) * t)
        g = round(top_color[1] + (bottom_color[1] - top_color[1]) * t)
        b = round(top_color[2] + (bottom_color[2] - top_color[2]) * t)
        draw.line([(0, y), (w, y)], fill=(r, g, b))
    return img


def main():
    img = build_gradient(SIZE, (255, 175, 130), (255, 122, 80))
    draw = ImageDraw.Draw(img)

    bear = Image.open("icons/icon-512.png").convert("RGBA")
    bear_size = 280
    bear = bear.resize((bear_size, bear_size), Image.LANCZOS)
    img.paste(bear, (90, (SIZE[1] - bear_size) // 2), bear)

    title_font = ImageFont.truetype(FONT_BOLD, 64)
    subtitle_font = ImageFont.truetype(FONT_REGULAR, 32)

    text_x = 430
    draw.text((text_x, 265), "아이랑 가볼까", font=title_font, fill="white")
    draw.text((text_x, 355), "전국 어디서나, 내 위치 기준 20km 나들이 지도", font=subtitle_font, fill="white")

    img.save(OUTPUT_PATH)
    print(f"og-image 재생성 완료 -> {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
