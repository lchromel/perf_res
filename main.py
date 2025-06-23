from fastapi import FastAPI, File, UploadFile, Form
from fastapi.responses import FileResponse
import os
from PIL import Image, ImageDraw, ImageFont
from typing import List

app = FastAPI()

def wrap_text(text, font, draw, max_width):
    words = text.split()
    lines = []
    current_line = ''
    for word in words:
        test_line = current_line + (' ' if current_line else '') + word
        w, _ = draw.textbbox((0, 0), test_line, font=font)[2:]
        if w <= max_width:
            current_line = test_line
        else:
            if current_line:
                lines.append(current_line)
            current_line = word
    if current_line:
        lines.append(current_line)
    return lines

def process_image(image_path, headline, subtitle, disclaimer, output_path="result.png", banner_size="auto"):
    with Image.open(image_path) as base_image:
        width, height = base_image.size
        aspect_ratio = width / height

        # Determine output sizes and overlay paths based on banner_size parameter
        if banner_size == "auto":
            # Auto-detect based on aspect ratio (original behavior)
            if abs(aspect_ratio - 1.0) < 0.15:
                output_sizes = [(1200, 1200)]
                overlay_paths = ["Overlay/1200x1200.png"]
            elif aspect_ratio > 1.0:
                output_sizes = [(1200, 628)]
                overlay_paths = ["Overlay/1200x628.png"]
            else:
                output_sizes = [(1200, 1500)]
                overlay_paths = ["Overlay/1200x1500.png"]
        else:
            # Use the specified banner size
            size_mapping = {
                "1200x1200": ("Overlay/1200x1200.png", (1200, 1200)),
                "1200x1500": ("Overlay/1200x1500.png", (1200, 1500)),
                "1200x628": ("Overlay/1200x628.png", (1200, 628)),
                "1080x1920": ("Overlay/1080x1920.png", (1080, 1920))
            }
            
            if banner_size not in size_mapping:
                # Default to 1200x1200 if invalid size provided
                overlay_path, output_size = size_mapping["1200x1200"]
                output_sizes = [output_size]
                overlay_paths = [overlay_path]
            else:
                overlay_path, output_size = size_mapping[banner_size]
                output_sizes = [output_size]
                overlay_paths = [overlay_path]

        results = []
        
        for i, (output_size, overlay_path) in enumerate(zip(output_sizes, overlay_paths)):
            # Generate unique output path for each size
            if len(output_sizes) == 1:
                current_output_path = output_path
            else:
                name, ext = os.path.splitext(output_path)
                current_output_path = f"{name}_{output_size[0]}x{output_size[1]}{ext}"

            # Cover and crop logic
            out_w, out_h = output_size
            scale = max(out_w / width, out_h / height)
            new_w = int(width * scale)
            new_h = int(height * scale)
            resized = base_image.resize((new_w, new_h), Image.LANCZOS)
            left = (new_w - out_w) // 2
            top = (new_h - out_h) // 2
            right = left + out_w
            bottom = top + out_h
            cropped = resized.crop((left, top, right, bottom))
            
            # Load and resize overlay
            with Image.open(overlay_path) as overlay_img:
                overlay = overlay_img.resize(output_size)
            
            # Create a new image for text
            text_layer = Image.new("RGBA", output_size, (0, 0, 0, 0))
            draw = ImageDraw.Draw(text_layer)

            # Set font sizes for each block and format
            if output_size in [(1200, 1200), (1200, 1500)]:
                headline_font = ImageFont.truetype("Fonts/YangoGroupHeadline-HeavyArabic.ttf", 124)
                subheadline_font = ImageFont.truetype("Fonts/YangoGroupText-Medium.ttf", 48)
                disclaimer_font = ImageFont.truetype("Fonts/YangoGroupText-Medium.ttf", 14)
            elif output_size == (1200, 628):
                headline_font = ImageFont.truetype("Fonts/YangoGroupHeadline-HeavyArabic.ttf", 92)
                subheadline_font = ImageFont.truetype("Fonts/YangoGroupText-Medium.ttf", 32)
                disclaimer_font = ImageFont.truetype("Fonts/YangoGroupText-Medium.ttf", 12)
            elif output_size == (1080, 1920):
                # Scale fonts proportionally for 1080x1920
                headline_font = ImageFont.truetype("Fonts/YangoGroupHeadline-HeavyArabic.ttf", 111)  # 124 * 1080/1200
                subheadline_font = ImageFont.truetype("Fonts/YangoGroupText-Medium.ttf", 43)  # 48 * 1080/1200
                disclaimer_font = ImageFont.truetype("Fonts/YangoGroupText-Medium.ttf", 13)  # 14 * 1080/1200
            else:
                headline_font = ImageFont.truetype("Fonts/YangoGroupHeadline-HeavyArabic.ttf", 72)
                subheadline_font = ImageFont.truetype("Fonts/YangoGroupText-Medium.ttf", 48)
                disclaimer_font = ImageFont.truetype("Fonts/YangoGroupText-Medium.ttf", 48)

            # Helper to get line spacing for each block type
            def get_line_spacing(font, block_type):
                if block_type == 'headline':
                    return int(font.size * 0.15)
                elif block_type == 'subheadline':
                    return int(font.size * 0.2)
                else:
                    return 10  # default for disclaimer

            # Calculate max text width
            if output_size == (1200, 628):
                max_text_width = 564
            else:
                shortest_side = min(out_w, out_h)
                max_text_width = int(shortest_side * 0.8)

            # 1200x1200, 1200x1500, and 1080x1920: anchor all text blocks to the bottom with 24px spacing between blocks, order: headline, subheadline, disclaimer
            if output_size in [(1200, 1200), (1200, 1500), (1080, 1920)]:
                blocks = []
                if headline:
                    headline_lines = wrap_text(headline, headline_font, draw, max_text_width)
                    blocks.append((headline_lines, headline_font, 'headline'))
                if subtitle:
                    subtitle_lines = wrap_text(subtitle, subheadline_font, draw, max_text_width)
                    blocks.append((subtitle_lines, subheadline_font, 'subheadline'))
                if disclaimer:
                    disclaimer_lines = wrap_text(disclaimer, disclaimer_font, draw, max_text_width)
                    blocks.append((disclaimer_lines, disclaimer_font, 'disclaimer'))
                # Calculate total height of all blocks (including spacing between blocks)
                block_heights = []
                for lines, font, block_type in blocks:
                    line_spacing = get_line_spacing(font, block_type)
                    block_height = sum([draw.textbbox((0, 0), line, font=font)[3] for line in lines]) + (len(lines)-1)*line_spacing
                    block_heights.append(block_height)
                # Calculate spacings between blocks
                spacings = []
                for i in range(len(blocks)-1):
                    if output_size == (1080, 1920) and blocks[i][2] == 'subheadline' and blocks[i+1][2] == 'disclaimer':
                        spacings.append(164)
                    else:
                        spacings.append(24)
                total_blocks_height = sum(block_heights) + sum(spacings)
                # Start y so the whole stack fits above the bottom margin
                y = out_h - 50 - total_blocks_height  # 50px bottom margin
                for idx, ((lines, font, block_type), block_height) in enumerate(zip(blocks, block_heights)):
                    line_spacing = get_line_spacing(font, block_type)
                    for lidx, line in enumerate(lines):
                        w, h = draw.textbbox((0, 0), line, font=font)[2:]
                        x = (out_w - w) // 2
                        draw.text((x, y), line, font=font, fill="white")
                        if lidx < len(lines) - 1:
                            y += h + line_spacing
                        else:
                            y += h
                    if idx < len(spacings):
                        y += spacings[idx]
            # 1200x628: anchor all text blocks to the top, 40px margin from top, 28px spacing between blocks
            elif output_size == (1200, 628):
                y = 40
                block_x = 40
                block_width = 540
                if headline:
                    lines = wrap_text(headline, headline_font, draw, max_text_width)
                    line_spacing = int(headline_font.size * 0.15)
                    for idx, line in enumerate(lines):
                        w, h = draw.textbbox((0, 0), line, font=headline_font)[2:]
                        x = block_x + (block_width - w) // 2
                        draw.text((x, y), line, font=headline_font, fill="white")
                        if idx < len(lines) - 1:
                            y += h + line_spacing
                        else:
                            y += h
                    y += 28
                if subtitle:
                    lines = wrap_text(subtitle, subheadline_font, draw, max_text_width)
                    line_spacing = int(subheadline_font.size * 0.2)
                    for idx, line in enumerate(lines):
                        w, h = draw.textbbox((0, 0), line, font=subheadline_font)[2:]
                        x = block_x + (block_width - w) // 2
                        draw.text((x, y), line, font=subheadline_font, fill="white")
                        if idx < len(lines) - 1:
                            y += h + line_spacing
                        else:
                            y += h
                    y += 28
                if disclaimer:
                    lines = wrap_text(disclaimer, disclaimer_font, draw, max_text_width)
                    # Calculate total height of disclaimer block
                    total_height = sum([draw.textbbox((0, 0), line, font=disclaimer_font)[3] for line in lines]) + (len(lines)-1)*10
                    y_disclaimer = out_h - 40 - total_height
                    for line in lines:
                        w, h = draw.textbbox((0, 0), line, font=disclaimer_font)[2:]
                        x = out_w - w - 40
                        draw.text((x, y_disclaimer), line, font=disclaimer_font, fill="white")
                        y_disclaimer += h + 10
            else:
                # Center-align headline with wrapping
                if headline:
                    lines = wrap_text(headline, headline_font, draw, max_text_width)
                    y = 100
                    line_spacing = int(headline_font.size * 0.15)
                    for idx, line in enumerate(lines):
                        w, h = draw.textbbox((0, 0), line, font=headline_font)[2:]
                        x = (out_w - w) // 2
                        draw.text((x, y), line, font=headline_font, fill="white")
                        if idx < len(lines) - 1:
                            y += h + line_spacing
                        else:
                            y += h
                # Center-align subtitle with wrapping
                if subtitle:
                    lines = wrap_text(subtitle, subheadline_font, draw, max_text_width)
                    y = 200
                    line_spacing = int(subheadline_font.size * 0.2)
                    for idx, line in enumerate(lines):
                        w, h = draw.textbbox((0, 0), line, font=subheadline_font)[2:]
                        x = (out_w - w) // 2
                        draw.text((x, y), line, font=subheadline_font, fill="white")
                        if idx < len(lines) - 1:
                            y += h + line_spacing
                        else:
                            y += h
                # Disclaimer alignment with wrapping
                if disclaimer:
                    lines = wrap_text(disclaimer, disclaimer_font, draw, max_text_width)
                    total_height = sum([draw.textbbox((0, 0), line, font=disclaimer_font)[3] for line in lines]) + (len(lines)-1)*10
                    y = out_h - 100 - total_height + 10  # Adjust so last line is at -100
                    for idx, line in enumerate(lines):
                        w, h = draw.textbbox((0, 0), line, font=disclaimer_font)[2:]
                        x = (out_w - w) // 2
                        draw.text((x, y), line, font=disclaimer_font, fill="white")
                        y += h + 10
            result = Image.alpha_composite(cropped.convert("RGBA"), overlay)
            result = Image.alpha_composite(result, text_layer)
            result.save(current_output_path)
            results.append(current_output_path)
        
        return results

@app.post("/process/")
async def process(
    image: UploadFile = File(...),
    headline: str = Form(""),
    subtitle: str = Form(""),
    disclaimer: str = Form(""),
    banner_size: str = Form("auto")
):
    input_path = f"input_{image.filename}"
    output_path = "result.png"
    with open(input_path, "wb") as f:
        f.write(await image.read())
    
    result_paths = process_image(input_path, headline, subtitle, disclaimer, output_path, banner_size)
    os.remove(input_path)
    
    # Return the generated result
    return FileResponse(result_paths[0], media_type="image/png", filename="result.png") 