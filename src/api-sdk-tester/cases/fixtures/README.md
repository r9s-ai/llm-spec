# API SDK Tester Fixtures

Shared test fixtures live here so cases can reference stable materials instead of embedding large
base64 strings directly in provider-specific case files.

Use `fixtures` from `./index.ts` for named fixtures, or the media readers for direct files:

- `readAudioFixtureBase64(fileName)`
- `readImageFixtureBase64(fileName)`
- `readVideoFixtureBase64(fileName)`
- `readMediaFixtureDataUri(type, fileName, mimeType)`

Current materials:

- `fixtures.audio.response2second`: short MP3 audio sample.
- `fixtures.images.hamburger`: JPEG image sample.
- `fixtures.video.office`: MP4 video sample.

Directory layout:

- `audio/`
- `images/`
- `video/`
