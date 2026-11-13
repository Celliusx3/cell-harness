# 04. Layer files and images

**Status.** done

## What to build

Move the four modules of `files` and of `images`. Neither has a router.
- `files/models.py` to `files/domain/models.py`
- `files/repository.py` to `files/repository/file_repository.py`
- `files/disk.py` to `files/repository/disk_file_repository.py`
- `files/service.py` to `files/service/file_service.py`
- `images/models.py` to `images/domain/models.py`
- `images/repository.py` to `images/repository/image_repository.py`
- `images/disk.py` to `images/repository/disk_image_repository.py`
- `images/service.py` to `images/service/image_service.py`

## Checks

- `make lint` passes, including the 300-line cap.
- `make test` passes with 2041 tests or more, coverage over 80%.
- `uv run python -c "import harness.web.server"` exits with no error.
- The layering test from ticket 01 passes for this package.

## Blocked by

01
