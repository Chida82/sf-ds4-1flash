# Vision fixtures

These small images test facts that a plausible generic description cannot
cover: exact OCR, diagram order, spatial relations, screenshot diagnostics,
photograph recognition, and rejection of an unrelated premise. The expected
facts live in `cases.json`.

sf-keep: the directory keeps its `glm53` name although GLM 5.3 is not in this
fork. The images are plain PNG and JPEG test data, and four kept tests read them
by this path -- `tests/test_jpeg_decode.py`, `tests/test_server_vision_agent.py`,
`tests/test_server_vision_cache.py` and `tests/test_server_vision_live_state.py`.
Renaming the directory would be a rename upstream never made, and every future
sync would conflict on it.

The GLM-specific quality runner that used to drive these images is gone.
Point the server tests above at a running `sf-ds4-1flash-server` with
`--vision gguf/DeepSeek-V4.1-Flash-Vision.gguf` instead.

`earth.jpg` is NASA's public-domain Apollo 17 image AS17-148-22727, downloaded
from Wikimedia Commons:
https://commons.wikimedia.org/wiki/File:Earth_apollo17.jpg
