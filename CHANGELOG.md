# Changelog

## [0.10.0] - 2026-05-01
### Features

- handle SQLMesh SQL files ([#291](https://github.com/amfaro/jarify/pull/291)) ([#291](https://github.com/amfaro/jarify/pull/291))

## [0.9.0] - 2026-05-01
### Features

- add prefer-ifnull-over-coalesce rule ([#289](https://github.com/amfaro/jarify/pull/289)) ([#289](https://github.com/amfaro/jarify/pull/289))

## [0.8.1] - 2026-05-01
### Bug Fixes

- remove no-select-star-in-cte; fold into no-select-star ([#285](https://github.com/amfaro/jarify/pull/285)) ([#285](https://github.com/amfaro/jarify/pull/285))

## [0.8.0] - 2026-05-01
### Features

- add rule catalog, `jarify rules` command, and kebab-case config keys ([#282](https://github.com/amfaro/jarify/pull/282)) ([#282](https://github.com/amfaro/jarify/pull/282))

## [0.7.0] - 2026-05-01
### Features

- add comment-based rule overrides ([#279](https://github.com/amfaro/jarify/pull/279)) ([#279](https://github.com/amfaro/jarify/pull/279))

## [0.6.2] - 2026-05-01
### Bug Fixes

- keep alias alignment stable across nested ctes ([#277](https://github.com/amfaro/jarify/pull/277)) ([#277](https://github.com/amfaro/jarify/pull/277))

## [0.6.1] - 2026-05-01
### Bug Fixes

- write unchanged stdin input to stdout ([#274](https://github.com/amfaro/jarify/pull/274)) ([#274](https://github.com/amfaro/jarify/pull/274))

## [0.6.0] - 2026-05-01
### Features

- align column aliases across query ([#272](https://github.com/amfaro/jarify/pull/272)) ([#272](https://github.com/amfaro/jarify/pull/272))

## [0.5.15] - 2026-05-01
### Bug Fixes

- keep ORDER BY ALL inline ([#269](https://github.com/amfaro/jarify/pull/269)) ([#269](https://github.com/amfaro/jarify/pull/269))

## [0.5.14] - 2026-05-01
### Bug Fixes

- improve case formatting ([#266](https://github.com/amfaro/jarify/pull/266)) ([#266](https://github.com/amfaro/jarify/pull/266))

### Documentation

- align style guide with current rules ([#262](https://github.com/amfaro/jarify/pull/262)) ([#262](https://github.com/amfaro/jarify/pull/262))

## [0.5.13] - 2026-04-30
### Bug Fixes

- preserve json extract grouping before casts ([#253](https://github.com/amfaro/jarify/pull/253)) ([#253](https://github.com/amfaro/jarify/pull/253))
- preserve custom transform macros ([#255](https://github.com/amfaro/jarify/pull/255)) ([#255](https://github.com/amfaro/jarify/pull/255))
- keep mixed agg group by explicit ([#256](https://github.com/amfaro/jarify/pull/256)) ([#256](https://github.com/amfaro/jarify/pull/256))
- preserve ORs near line comments ([#257](https://github.com/amfaro/jarify/pull/257)) ([#257](https://github.com/amfaro/jarify/pull/257))
- preserve dynamic json_extract paths ([#258](https://github.com/amfaro/jarify/pull/258)) ([#258](https://github.com/amfaro/jarify/pull/258))

## [0.5.12] - 2026-04-29
### Bug Fixes

- emit if(cond, val, NULL) for no-ELSE CASE rewrites ([#245](https://github.com/amfaro/jarify/pull/245)) ([#245](https://github.com/amfaro/jarify/pull/245))

## [0.5.11] - 2026-04-29
### Bug Fixes

- align single-line aliases when SELECT has multi-line alias ([#240](https://github.com/amfaro/jarify/pull/240)) ([#240](https://github.com/amfaro/jarify/pull/240))

## [0.5.10] - 2026-04-29
### Bug Fixes

- keep AND/OR connector inline when it fits within max_line_length ([#237](https://github.com/amfaro/jarify/pull/237)) ([#237](https://github.com/amfaro/jarify/pull/237))

## [0.5.9] - 2026-04-29
### Bug Fixes

- wrap overlong branches in wide if() ([#234](https://github.com/amfaro/jarify/pull/234)) ([#234](https://github.com/amfaro/jarify/pull/234))

## [0.5.8] - 2026-04-29
### Bug Fixes

- expand wide if() to leading-comma 5-line form
- align wide if() expansion with leading-comma style
- indent if() args one level inside the opening paren
- align if() closing paren with CASE END at pad columns

## [0.5.7] - 2026-04-28
### Bug Fixes

- remove CASE fallback from if_sql — always emit IF() ([#230](https://github.com/amfaro/jarify/pull/230)) ([#230](https://github.com/amfaro/jarify/pull/230))

## [0.5.6] - 2026-04-28
### Bug Fixes

- use compact args in if_sql to prevent mid-condition wrap ([#227](https://github.com/amfaro/jarify/pull/227)) ([#227](https://github.com/amfaro/jarify/pull/227))

## [0.5.5] - 2026-04-28
### Bug Fixes

- align struct closing paren and wrap wide lambdas ([#224](https://github.com/amfaro/jarify/pull/224)) ([#224](https://github.com/amfaro/jarify/pull/224))

## [0.5.4] - 2026-04-28
### Bug Fixes

- bypass leading-comma path for DataType in expressions() ([#220](https://github.com/amfaro/jarify/pull/220)) ([#220](https://github.com/amfaro/jarify/pull/220))

## [0.5.3] - 2026-04-28
### Bug Fixes

- use prev_anchor to disambiguate duplicate anchor text ([#217](https://github.com/amfaro/jarify/pull/217)) ([#217](https://github.com/amfaro/jarify/pull/217))

## [0.5.2] - 2026-04-28
### Bug Fixes

- keep IN (SELECT ...) inline when it fits within max line length ([#214](https://github.com/amfaro/jarify/pull/214)) ([#214](https://github.com/amfaro/jarify/pull/214))

### Documentation

- add test-integrity skill to guard against suppressing failures ([#212](https://github.com/amfaro/jarify/pull/212)) ([#212](https://github.com/amfaro/jarify/pull/212))

## [0.5.1] - 2026-04-28
### Bug Fixes

- treat list() as aggregate in prefer-group-by-all ([#210](https://github.com/amfaro/jarify/pull/210)) ([#210](https://github.com/amfaro/jarify/pull/210))

## [0.5.0] - 2026-04-27
### Features

- add prefer-if-over-case rule — rewrite single-WHEN CASE to IF() ([#208](https://github.com/amfaro/jarify/pull/208)) ([#208](https://github.com/amfaro/jarify/pull/208))

## [0.4.0] - 2026-04-27
### Features

- add prefer-neq-operator rule — rewrite <> to != ([#206](https://github.com/amfaro/jarify/pull/206)) ([#206](https://github.com/amfaro/jarify/pull/206))

## [0.3.3] - 2026-04-27
### Bug Fixes

- place trailing rust fmt placeholder before statement terminator ([#201](https://github.com/amfaro/jarify/pull/201)) ([#201](https://github.com/amfaro/jarify/pull/201))

## [0.3.2] - 2026-04-27
### Bug Fixes

- handle mixed agg/non-agg SELECT exprs in prefer-group-by-all ([#198](https://github.com/amfaro/jarify/pull/198)) ([#198](https://github.com/amfaro/jarify/pull/198))

## [0.3.1] - 2026-04-27
### Bug Fixes

- preserve bare numeric/decimal without injecting default precision ([#195](https://github.com/amfaro/jarify/pull/195)) ([#195](https://github.com/amfaro/jarify/pull/195))

## [0.3.0] - 2026-04-27
### Features

- promote prefer-group-by-all to auto-fix formatter rule ([#192](https://github.com/amfaro/jarify/pull/192)) ([#192](https://github.com/amfaro/jarify/pull/192))

## [0.2.0] - 2026-04-27
### Features

- always emit CASE expressions as multi-line in pretty mode ([#189](https://github.com/amfaro/jarify/pull/189)) ([#189](https://github.com/amfaro/jarify/pull/189))

## [0.1.34] - 2026-04-27
### Bug Fixes

- strip AS from UNNEST function aliases ([#185](https://github.com/amfaro/jarify/pull/185)) ([#185](https://github.com/amfaro/jarify/pull/185))

## [0.1.33] - 2026-04-27
### Bug Fixes

- normalise OUTER before computing join alias alignment width ([#182](https://github.com/amfaro/jarify/pull/182)) ([#182](https://github.com/amfaro/jarify/pull/182))

## [0.1.32] - 2026-04-25
### Bug Fixes

- remove extra space before column list in UNNEST table aliases ([#179](https://github.com/amfaro/jarify/pull/179)) ([#179](https://github.com/amfaro/jarify/pull/179))

## [0.1.31] - 2026-04-25
### Bug Fixes

- preserve string_agg name and inline ORDER BY in aggregates ([#176](https://github.com/amfaro/jarify/pull/176)) ([#176](https://github.com/amfaro/jarify/pull/176))

## [0.1.30] - 2026-04-25
### Bug Fixes

- preserve between-column -- comments in SELECT lists ([#173](https://github.com/amfaro/jarify/pull/173)) ([#173](https://github.com/amfaro/jarify/pull/173))

## [0.1.29] - 2026-04-24
### Bug Fixes

- preserve multi-line leading comment blocks ([#170](https://github.com/amfaro/jarify/pull/170)) ([#170](https://github.com/amfaro/jarify/pull/170))

## [0.1.28] - 2026-04-24
### Bug Fixes

- handle whole-line placeholder as CTAS body ([#167](https://github.com/amfaro/jarify/pull/167)) ([#167](https://github.com/amfaro/jarify/pull/167))

## [0.1.27] - 2026-04-24
### Bug Fixes

- preserve AS alignment when SELECT contains Rust format placeholder strings ([#164](https://github.com/amfaro/jarify/pull/164)) ([#164](https://github.com/amfaro/jarify/pull/164))

## [0.1.26] - 2026-04-24
### Bug Fixes

- render -> and ->> operators without surrounding spaces ([#161](https://github.com/amfaro/jarify/pull/161)) ([#161](https://github.com/amfaro/jarify/pull/161))

## [0.1.25] - 2026-04-24
### Bug Fixes

- keep short OR/AND conditions inline in WHERE/HAVING when they fit ([#158](https://github.com/amfaro/jarify/pull/158)) ([#158](https://github.com/amfaro/jarify/pull/158))

## [0.1.24] - 2026-04-24
### Bug Fixes

- use -- for single-line comments instead of /* */ everywhere ([#155](https://github.com/amfaro/jarify/pull/155)) ([#155](https://github.com/amfaro/jarify/pull/155))

## [0.1.23] - 2026-04-24
### Bug Fixes

- preserve leading comments before CTE definitions ([#152](https://github.com/amfaro/jarify/pull/152)) ([#152](https://github.com/amfaro/jarify/pull/152))

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


