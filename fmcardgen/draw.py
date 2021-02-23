from PIL import Image, ImageFont, ImageDraw
from .config import CardGenConfig, PaddingConfig, TextFieldConfig, DEFAULT_FONT
from .frontmatter import (
    get_frontmatter_list,
    get_frontmatter_value,
    get_frontmatter_formatted,
)
from pydantic.color import Color
from typing import List, Tuple, Mapping, cast, Union, Optional
from textwrap import TextWrapper
import dateutil.parser


def draw(fm: dict, cnf: CardGenConfig) -> Image.Image:
    im = Image.open(cnf.template)

    for field in cnf.text_fields:
        parser = dateutil.parser.parse if field.parse == "datetime" else None

        if field.multi:
            values = get_frontmatter_list(
                fm,
                source=str(field.source),
                default=str(field.default),
                missing_ok=field.optional,
                parser=parser,
            )
            if field.format:
                values = [
                    field.format.format(v, **{str(field.source): v}) for v in values
                ]
            draw_tag_field(im, values, field)

        elif isinstance(field.source, list):
            if isinstance(field.default, Mapping):
                defaults = field.default
            else:
                defaults = {source: field.default or "" for source in field.source}

            value = get_frontmatter_formatted(
                fm,
                format=str(field.format),
                sources=field.source,
                defaults=defaults,
                missing_ok=field.optional,
            )
            draw_text_field(im, str(value), field)

        else:
            value = get_frontmatter_value(
                fm,
                source=field.source,
                default=(
                    field.default.get(field.source, None)
                    if isinstance(field.default, Mapping)
                    else field.default
                ),
                missing_ok=field.optional,
                parser=parser,
            )
            if field.format:
                value = field.format.format(value, **{field.source: value})
            draw_text_field(im, str(value), field)

    return im


def draw_text_field(im: Image.Image, text: str, field: TextFieldConfig) -> None:
    font = load_font(str(field.font), field.font_size)

    if field.wrap:
        max_width = field.max_width if field.max_width else im.width - field.x
        text = wrap_font_text(font, text, max_width)

    draw = ImageDraw.Draw(im, mode="RGBA")

    if field.bg:
        assert isinstance(field.padding, PaddingConfig)  # for mypy
        _draw_rect(
            im=im,
            bbox=draw.textbbox(xy=(field.x, field.y), text=text, font=font),
            padding=field.padding,
            color=field.bg,
        )

    assert isinstance(field.fg, Color)  # for mypy
    draw.text(xy=(field.x, field.y), text=text, font=font, fill=to_pil_color(field.fg))


def draw_tag_field(im: Image.Image, tags: List[str], field: TextFieldConfig) -> None:
    assert isinstance(field.padding, PaddingConfig)  # for mypy

    font = load_font(str(field.font), field.font_size)

    draw = ImageDraw.Draw(im)
    xy = (field.x, field.y)
    spacing = field.spacing + field.padding.left + field.padding.right

    # Calculate the height of all the text, and use that as the height for each
    # individual box If we don't do this, different boxes could have different
    # calculated heights because of ascenders/descenders.
    _, height = draw.textsize(text=" ".join(tags), font=font)

    for tag in tags:
        width = draw.textlength(text=tag, font=font)

        if field.bg:
            _draw_rect(
                im=im,
                bbox=(xy[0], xy[1], xy[0] + width, xy[1] + height),
                padding=field.padding,
                color=field.bg,
            )

        assert isinstance(field.fg, Color)
        draw.text(xy=xy, text=tag, font=font, fill=to_pil_color(field.fg))
        xy = (xy[0] + width + spacing, xy[1])


def _draw_rect(
    im: Image.Image,
    bbox: Tuple[int, int, int, int],
    padding: PaddingConfig,
    color: Color,
):
    x0, y0, x1, y1 = bbox

    # expand the bounding box to account for padding
    x0 -= padding.left
    y0 -= padding.top
    x1 += padding.right
    y1 += padding.bottom

    # When drawing with any transparancy, just drawing directly on to
    # the background image doesn't actually do compositing, you just get
    # a semi-transparant "cutout" of the background. To work around this,
    # draw into a temporary image and then composite it.
    overlay = Image.new(mode="RGBA", size=im.size, color=(0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    draw.rectangle(
        xy=(x0, y0, x1, y1),
        fill=to_pil_color(color),
    )
    im.alpha_composite(overlay)


def wrap_font_text(font: ImageFont.ImageFont, text: str, max_width: int) -> str:
    wrapper = TextWrapper()
    chunks = wrapper._split_chunks(text)

    lines: List[List[str]] = []
    cur_line: List[str] = []
    cur_line_width = 0

    for chunk in chunks:
        width, _ = font.getsize(chunk)

        # If this chunk makes our line too long...
        if cur_line_width + width > max_width:
            # Special case: a single chunk that's too long to fit on one line.
            # In that case just use that chunk as a line by itself, otherwise
            # we'll enter an infinate loop here.
            if cur_line_width == 0:
                lines.append([chunk])
                cur_line = []
                cur_line_width = 0
                continue

            lines.append(cur_line)
            cur_line = [] if chunk.isspace() else [chunk]
            cur_line_width = width

        else:
            cur_line.append(chunk)
            cur_line_width += width

    if cur_line:
        lines.append(cur_line)

    return "\n".join("".join(line).strip() for line in lines)


def load_font(font: str, size: Optional[int]) -> ImageFont.ImageFont:
    if font == DEFAULT_FONT:
        return ImageFont.load_default()
    else:
        return ImageFont.truetype(font, size)


PILColorTuple = Union[Tuple[int, int, int], Tuple[int, int, int, int]]


def to_pil_color(color: Color) -> PILColorTuple:
    """
    Convert a pydantic Color to a PIL color 4-tuple

    Color.as_rgb_tuple() _almost_ works, but it returns the alpha channel as
    a float between 0 and 1, and PIL expects an int 0-255
    """
    # cast() business is a mypy workaround for
    # https://github.com/python/mypy/issues/1178
    c = color.as_rgb_tuple()
    if len(c) == 3:
        return cast(Tuple[int, int, int], c)
    else:
        r, g, b, a = cast(Tuple[int, int, int, float], c)
        return r, g, b, round(a * 255)
