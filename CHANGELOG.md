# Changelog

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


