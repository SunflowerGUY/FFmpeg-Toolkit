from PIL import Image, ImageEnhance
import struct

def generate_multi_res_ico(source_path="icon_source.jpg", ico_path="app_icon.ico", background_mode="white_rounded"):
    img = Image.open(source_path).convert("RGBA")
    
    if background_mode == "white_rounded":
        # Create a crisp white rounded rectangle badge/tile behind the dark icon graphics
        # so it stands out cleanly on black, dark, and light wallpapers alike.
        base_w, base_h = img.size
        
        # 1. Isolate the foreground content (red ff and dark wrenches)
        pixels = list(img.get_flattened_data()) if hasattr(img, "get_flattened_data") else list(img.getdata())
        fg_pixels = []
        for r, g, b, a in pixels:
            brightness = (r + g + b) / 3.0
            if brightness > 248:
                fg_pixels.append((255, 255, 255, 0))
            elif brightness > 220:
                alpha = int(255 * (255 - brightness) / 28.0)
                fg_pixels.append((r, g, b, max(0, min(255, alpha))))
            else:
                fg_pixels.append((r, g, b, 255))
        
        fg_img = Image.new("RGBA", (base_w, base_h))
        fg_img.putdata(fg_pixels)
        
        # 2. Draw a smooth white rounded rectangle tile
        from PIL import ImageDraw
        bg_tile = Image.new("RGBA", (base_w, base_h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(bg_tile)
        
        # Corner radius (~18% of tile size for standard Windows app icon style)
        corner_radius = int(base_w * 0.18)
        padding = int(base_w * 0.02) # minimal inset border
        
        draw.rounded_rectangle(
            [padding, padding, base_w - padding - 1, base_h - padding - 1],
            radius=corner_radius,
            fill=(255, 255, 255, 255)
        )
        
        # 3. Composite foreground over the white rounded tile
        composite = Image.alpha_composite(bg_tile, fg_img)
        img = composite

    sizes = [(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (24, 24), (16, 16)]
    scaled_images = []
    
    for s in sizes:
        # Resize with high-quality LANCZOS filter
        scaled = img.resize(s, Image.Resampling.LANCZOS)
        # Apply sharpness boost for smaller desktop icon sizes to keep edges crisp
        if s[0] <= 64:
            enhancer = ImageEnhance.Sharpness(scaled)
            scaled = enhancer.enhance(1.6)
        scaled_images.append(scaled)

    # Save multi-resolution ICO with all pre-rendered sizes
    scaled_images[0].save(
        ico_path,
        format="ICO",
        sizes=[im.size for im in scaled_images],
        append_images=scaled_images[1:]
    )
    print(f"Successfully generated razor-sharp multi-resolution ICO at {ico_path}")

    # Inspect generated ICO binary
    with open(ico_path, "rb") as f:
        reserved, ico_type, count = struct.unpack("<HHH", f.read(6))
        print(f"ICO header: type={ico_type}, image_count={count}")
        for i in range(count):
            w, h, colors, res, planes, bpp, size, offset = struct.unpack("<BBBBHHII", f.read(16))
            w = 256 if w == 0 else w
            h = 256 if h == 0 else h
            print(f"  Layer {i}: {w}x{h}, bpp={bpp}, size_bytes={size}")

if __name__ == "__main__":
    generate_multi_res_ico()
