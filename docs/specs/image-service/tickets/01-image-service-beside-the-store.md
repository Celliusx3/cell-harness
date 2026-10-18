# 01 · The image service, beside the old store

**Status.** done

**What to build.** A new package `backend/harness/images/`:
- `models.py`: `ImageFile` (`path`, `media_type`), replacing `StoredImage`.
- `repository.py`: the `ImageRepository` protocol (`write(sha256, media_type, data)`, `read(sha256, media_type) -> bytes`, `file_of(sha256) -> ImageFile | None`) and `KEPT_MEDIA_TYPES`.
- `disk.py`: `DiskImageRepository(root)`, with the storage half of `ImageStore`: atomic write once, under `<sha256>.<ext>`.
- `service.py`: `ImageService(repository)`, holding the rules: `of_result(returned)`, `of_attachments(files)`, `read(image)` with the hash check, `file_of(sha256)`, `is_sha256`, `IMAGE_MAX_BYTES`.

The old `session/images.py` and `runtime/images.py` stay until ticket 02.

**Checks.** `test_disk_images.py` (storage) and `test_image_service.py` (rules) carry every test of `test_image_store.py` with the same names. `test_image_service.py` also tests `of_result` and `of_attachments` directly: the 5 MB note, a type no model is sent, a file that is not an image, a file that cannot be read, an image that cannot be kept. All pass, and the whole backend suite stays green. `test_runtime_images.py` tests the turn loop and stays; ticket 02 points it at the service.

**Blocked by.** none
