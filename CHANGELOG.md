# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog], and this project adheres to [Semantic Versioning].

## [0.2.0] - 2023-04-07

### Added

- Python 3.11 support.
- macOS and arm64 support.

### Fixed

- Fixed client streaming methods.

### Other

- `websockets` library updated to 10.4.

## [0.1.2] - 2022-05-24

### Improved

- Now `max_size` argument can be None to disable message size limit. 

### Fixed

- Fixed crash with "Cannot connect while not disconnected".

### Other

- `websockets` library updated to 10.3.

## [0.1.1] - 2022-01-06

### Fixed

- Fixed exceptions raised on server error.

## [0.1.0] - 2021-11-22

Initial release.

<!-- Links -->
[keep a changelog]: https://keepachangelog.com/en/1.0.0/
[semantic versioning]: https://semver.org/spec/v2.0.0.html

<!-- Versions -->
[Unreleased]: https://github.com/dipdup-io/dipdup/compare/0.2.0...HEAD
[0.2.0]: https://github.com/dipdup-io/dipdup/compare/0.1.2...0.2.0
[0.1.2]: https://github.com/dipdup-io/dipdup/compare/0.1.1...0.1.2
[0.1.1]: https://github.com/dipdup-io/dipdup/compare/0.1.0...0.1.1
[0.1.0]: https://github.com/dipdup-io/dipdup/releases/tag/0.1.0
