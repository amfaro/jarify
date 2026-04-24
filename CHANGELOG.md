# Changelog

## [0.1.22] - 2026-04-24
### Bug Fixes

- preserve leading comments on their own line in SELECT columns ([#149](https://github.com/amfaro/jarify/pull/149)) ([#149](https://github.com/amfaro/jarify/pull/149))

## [0.1.21] - 2026-04-24
### Bug Fixes

- preserve SELECT when * EXCLUDE or * REPLACE is used ([#146](https://github.com/amfaro/jarify/pull/146)) ([#146](https://github.com/amfaro/jarify/pull/146))

## [0.1.20] - 2026-04-24
### Bug Fixes

- only align WHERE = operators across top-level AND conditions ([#143](https://github.com/amfaro/jarify/pull/143)) ([#143](https://github.com/amfaro/jarify/pull/143))

## [0.1.19] - 2026-04-24
### Bug Fixes

- keep CASE WHEN conditions compact when AND chain is present ([#140](https://github.com/amfaro/jarify/pull/140)) ([#140](https://github.com/amfaro/jarify/pull/140))

## [0.1.18] - 2026-04-24
### Bug Fixes

- preserve -- line comments on SELECT column expressions ([#137](https://github.com/amfaro/jarify/pull/137)) ([#137](https://github.com/amfaro/jarify/pull/137))

## [0.1.17] - 2026-04-24
### Bug Fixes

- keep parenthesized expressions inline when they fit within max_line_length ([#134](https://github.com/amfaro/jarify/pull/134)) ([#134](https://github.com/amfaro/jarify/pull/134))

## [0.1.16] - 2026-04-24
### Bug Fixes

- regenerate uv.lock after version bump ([#129](https://github.com/amfaro/jarify/pull/129)) ([#129](https://github.com/amfaro/jarify/pull/129))
- guard FROM-first conversion behind self.pretty in select_sql ([#131](https://github.com/amfaro/jarify/pull/131)) ([#131](https://github.com/amfaro/jarify/pull/131))

## [0.1.15] - 2026-04-24
### Bug Fixes

- keep WHEN/THEN inline and suppress connector expansion in CASE branches ([#127](https://github.com/amfaro/jarify/pull/127)) ([#127](https://github.com/amfaro/jarify/pull/127))

## [0.1.14] - 2026-04-23
### Bug Fixes

- convert 2-argument coalesce to ifnull ([#124](https://github.com/amfaro/jarify/pull/124)) ([#124](https://github.com/amfaro/jarify/pull/124))

## [0.1.13] - 2026-04-23
### Bug Fixes

- preserve ifnull instead of converting to coalesce ([#120](https://github.com/amfaro/jarify/pull/120)) ([#120](https://github.com/amfaro/jarify/pull/120))

## [0.1.12] - 2026-04-23
### Bug Fixes

- remove = operator alignment in WHERE clauses ([#117](https://github.com/amfaro/jarify/pull/117)) ([#117](https://github.com/amfaro/jarify/pull/117))

## [0.1.11] - 2026-04-23
### Bug Fixes

- lowercase boolean literals (true/false) ([#114](https://github.com/amfaro/jarify/pull/114)) ([#114](https://github.com/amfaro/jarify/pull/114))

## [0.1.10] - 2026-04-23
### Bug Fixes

- preserve blank lines between placeholder blocks and SQL ([#111](https://github.com/amfaro/jarify/pull/111)) ([#111](https://github.com/amfaro/jarify/pull/111))

## [0.1.9] - 2026-04-23
### Bug Fixes

- preserve consecutive whole-line template placeholder order ([#108](https://github.com/amfaro/jarify/pull/108)) ([#108](https://github.com/amfaro/jarify/pull/108))

## [0.1.8] - 2026-04-23
### Bug Fixes

- preserve indentation of whole-line template placeholders ([#105](https://github.com/amfaro/jarify/pull/105)) ([#105](https://github.com/amfaro/jarify/pull/105))

## [0.1.7] - 2026-04-23
### Bug Fixes

- auto-rewrite comma joins to explicit CROSS JOIN ([#100](https://github.com/amfaro/jarify/pull/100)) ([#100](https://github.com/amfaro/jarify/pull/100))

## [0.1.6] - 2026-04-23
### Bug Fixes

- preserve comma joins and extend FROM-first to multi-table queries ([#97](https://github.com/amfaro/jarify/pull/97)) ([#97](https://github.com/amfaro/jarify/pull/97))

## [0.1.5] - 2026-04-22
### Bug Fixes

- preserve list_contains function name ([#94](https://github.com/amfaro/jarify/pull/94)) ([#94](https://github.com/amfaro/jarify/pull/94))

## [0.1.4] - 2026-04-22
### Bug Fixes

- keep inline subquery in FROM on one line when it fits ([#92](https://github.com/amfaro/jarify/pull/92)) ([#92](https://github.com/amfaro/jarify/pull/92))

## [0.1.3] - 2026-04-22
### Bug Fixes

- prevent double space before TABLE in AS TABLE macro return type ([#90](https://github.com/amfaro/jarify/pull/90)) ([#90](https://github.com/amfaro/jarify/pull/90))

### Documentation

- document automated release workflow ([#86](https://github.com/amfaro/jarify/pull/86)) ([#86](https://github.com/amfaro/jarify/pull/86))

## [0.1.2] - 2026-04-15
### Bug Fixes

- suppress no-select-star for FROM-first candidates when prefer_from_first is enabled ([#76](https://github.com/amfaro/jarify/pull/76)) ([#76](https://github.com/amfaro/jarify/pull/76))
- use --bumped-version flag in release prepare script ([#78](https://github.com/amfaro/jarify/pull/78)) ([#78](https://github.com/amfaro/jarify/pull/78))

### Refactoring

- add LintOnlyRule base class to eliminate apply() no-op ([#80](https://github.com/amfaro/jarify/pull/80)) ([#80](https://github.com/amfaro/jarify/pull/80))

## [0.1.1] - 2026-04-15
### Bug Fixes

- TTY-aware diff output and explicit NO_COLOR support ([#63](https://github.com/amfaro/jarify/pull/63)) ([#63](https://github.com/amfaro/jarify/pull/63))
- lint violations now report accurate line and column positions ([#66](https://github.com/amfaro/jarify/pull/66)) ([#66](https://github.com/amfaro/jarify/pull/66))

### Features

- add --format json to jarify lint ([#62](https://github.com/amfaro/jarify/pull/62)) ([#62](https://github.com/amfaro/jarify/pull/62))

## [0.1.0] - 2026-04-14
### Bug Fixes

- place CTE inline comments after AS as line comments ([#47](https://github.com/amfaro/jarify/pull/47)) ([#47](https://github.com/amfaro/jarify/pull/47))
- align = operators in WHERE clause conditions ([#49](https://github.com/amfaro/jarify/pull/49)) ([#49](https://github.com/amfaro/jarify/pull/49))
- put IN subquery opening paren on its own line ([#51](https://github.com/amfaro/jarify/pull/51)) ([#51](https://github.com/amfaro/jarify/pull/51))

### Documentation

- add SQL style guide with bad/good examples for all rules ([#17](https://github.com/amfaro/jarify/pull/17)) ([#17](https://github.com/amfaro/jarify/pull/17))
- fix type cast direction and add CTE naming convention ([#19](https://github.com/amfaro/jarify/pull/19)) ([#19](https://github.com/amfaro/jarify/pull/19))

### Features

- rewrite SELECT * as FROM-first DuckDB syntax ([#21](https://github.com/amfaro/jarify/pull/21)) ([#21](https://github.com/amfaro/jarify/pull/21))
- add 6 new formatting and lint rules ([#24](https://github.com/amfaro/jarify/pull/24)) ([#24](https://github.com/amfaro/jarify/pull/24))
- format CREATE TABLE with aligned columns and own-line paren ([#27](https://github.com/amfaro/jarify/pull/27)) ([#27](https://github.com/amfaro/jarify/pull/27))
- inline first WHERE/HAVING condition with aligned AND/OR ([#30](https://github.com/amfaro/jarify/pull/30)) ([#30](https://github.com/amfaro/jarify/pull/30))
- uppercase aggregate and window function names ([#31](https://github.com/amfaro/jarify/pull/31)) ([#31](https://github.com/amfaro/jarify/pull/31))
- align FROM/JOIN aliases and inline ON conditions ([#33](https://github.com/amfaro/jarify/pull/33)) ([#33](https://github.com/amfaro/jarify/pull/33))
- publish jarify to PyPI via OIDC trusted publishing ([#61](https://github.com/amfaro/jarify/pull/61)) ([#61](https://github.com/amfaro/jarify/pull/61))

## [0.0.1] - 2026-04-10
### Bug Fixes

- handle PIVOT ... USING ... ORDER BY without warning ([#3](https://github.com/amfaro/jarify/pull/3)) ([#3](https://github.com/amfaro/jarify/pull/3))
- use dopplerhq/secrets-fetch-action@v2 ([#13](https://github.com/amfaro/jarify/pull/13)) ([#13](https://github.com/amfaro/jarify/pull/13))
- pin dopplerhq/secrets-fetch-action to v2.0.0 ([#14](https://github.com/amfaro/jarify/pull/14)) ([#14](https://github.com/amfaro/jarify/pull/14))
- add doppler-project and doppler-config inputs ([#15](https://github.com/amfaro/jarify/pull/15)) ([#15](https://github.com/amfaro/jarify/pull/15))

### Features

- initialize jarify MVP — DuckDB SQL linter and formatter
- implement phases 3, 5, and 6 of MVP plan
- implement company-style formatting with leading commas and CTE style
- add README, CI/publish workflows, and project URLs
- semicolons on own line, AS alignment, graceful parse errors ([#1](https://github.com/amfaro/jarify/pull/1)) ([#1](https://github.com/amfaro/jarify/pull/1))


