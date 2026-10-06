from io import BytesIO

from fastapi.testclient import TestClient
from PIL import Image

from app.main import app


client = TestClient(app)


def make_image_bytes(
    image_format: str,
    size: tuple[int, int] = (100, 100),
) -> bytes:
    buffer = BytesIO()

    image = Image.new(
        "RGB",
        size,
        color="white",
    )

    image.save(
        buffer,
        format=image_format,
    )

    return buffer.getvalue()


def test_valid_jpeg_upload():
    image_bytes = make_image_bytes("JPEG")

    response = client.post(
        "/api/vision/upload",
        files={
            "image": (
                "leaf.jpg",
                image_bytes,
                "image/jpeg",
            )
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "valid"
    assert data["filename"] == "leaf.jpg"
    assert data["content_type"] == "image/jpeg"
    assert data["image_format"] == "JPEG"
    assert data["width"] == 100
    assert data["height"] == 100
    assert data["message"] == "Image accepted for visual analysis."


def test_valid_png_upload():
    image_bytes = make_image_bytes("PNG")

    response = client.post(
        "/api/vision/upload",
        files={
            "image": (
                "leaf.png",
                image_bytes,
                "image/png",
            )
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "valid"
    assert data["image_format"] == "PNG"
    assert data["width"] == 100
    assert data["height"] == 100


def test_valid_webp_upload():
    image_bytes = make_image_bytes("WEBP")

    response = client.post(
        "/api/vision/upload",
        files={
            "image": (
                "leaf.webp",
                image_bytes,
                "image/webp",
            )
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "valid"
    assert data["image_format"] == "WEBP"


def test_invalid_file_type():
    response = client.post(
        "/api/vision/upload",
        files={
            "image": (
                "notes.txt",
                b"this is not an image",
                "text/plain",
            )
        },
    )

    assert response.status_code == 400

    data = response.json()

    assert "Unsupported image MIME type" in data["detail"]


def test_corrupt_image():
    response = client.post(
        "/api/vision/upload",
        files={
            "image": (
                "broken.jpg",
                b"this is corrupt image data",
                "image/jpeg",
            )
        },
    )

    assert response.status_code == 400

    data = response.json()

    assert "valid or readable image" in data["detail"]


def test_oversized_image():
    oversized_bytes = b"x" * (10 * 1024 * 1024 + 1)

    response = client.post(
        "/api/vision/upload",
        files={
            "image": (
                "large.jpg",
                oversized_bytes,
                "image/jpeg",
            )
        },
    )

    assert response.status_code == 400

    data = response.json()

    assert "exceeds maximum allowed size" in data["detail"]
