# API SDK Tester Fixtures

Shared test fixtures live here so cases can reference stable materials instead of embedding large
base64 strings directly in provider-specific case files.

Use `IMAGE_INPUT_FIXTURES` and `MEDIA_INPUT_FIXTURES` from `../fixtures.ts` for named fixtures, or
the fixture readers for direct files:

- `readFixtureBase64(fileName)`
- `createFixtureDataUri(mimeType, fileName)`
- `createFixtureFile(fileName, name, mimeType)`

Directory layout:

- `audio/`
- `images/`
- `video/`
