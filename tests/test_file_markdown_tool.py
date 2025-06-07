from PIL import Image
from src.backend.tools.file_markdown_tool import split_image


def create_image(width, height):
    return Image.new('RGB', (width, height), color='white')


def test_split_image_no_split():
    img = create_image(100, 100)
    result = split_image(img, max_height=200, max_width=200)
    assert len(result) == 1


def test_split_image_vertical():
    img = create_image(100, 500)
    result = split_image(img, max_height=200, max_width=200)
    assert len(result) == 3  # ceil(500/200)
    assert all(im.size[0] == 100 for im in result)


def test_split_image_horizontal():
    img = create_image(500, 100)
    result = split_image(img, max_height=200, max_width=200)
    assert len(result) == 3
    assert all(im.size[1] == 100 for im in result)
