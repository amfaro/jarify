# Changelog

## [0.16.0] - 2026-10-29
### Bug Fixes

- let publish push the release tag ([#404](https://github.com/amfaro/jarify/pull/404)) ([#404](https://github.com/amfaro/jarify/pull/404))
- keep a recursive CTE's USING KEY ([#405](https://github.com/amfaro/jarify/pull/405)) ([#405](https://github.com/amfaro/jarify/pull/405))
- keep BOOL_OR and BOOL_AND arguments as written ([#406](https://github.com/amfaro/jarify/pull/406)) ([#406](https://github.com/amfaro/jarify/pull/406))
- write FILTER (WHERE …) with a space after FILTER ([#407](https://github.com/amfaro/jarify/pull/407)) ([#407](https://github.com/amfaro/jarify/pull/407))
- keep struct_pack(name := value) as written ([#410](https://github.com/amfaro/jarify/pull/410)) ([#410](https://github.com/amfaro/jarify/pull/410))
- mask macros with markers as wide as the macro ([#411](https://github.com/amfaro/jarify/pull/411)) ([#411](https://github.com/amfaro/jarify/pull/411))
- write EXISTS (…) with a space after EXISTS ([#412](https://github.com/amfaro/jarify/pull/412)) ([#412](https://github.com/amfaro/jarify/pull/412))

### Documentation

- refresh 16 examples to jarify's current output ([#409](https://github.com/amfaro/jarify/pull/409)) ([#409](https://github.com/amfaro/jarify/pull/409))

### Features

- align a set operation's branches and its CTEs on one AS column ([#408](https://github.com/amfaro/jarify/pull/408)) ([#408](https://github.com/amfaro/jarify/pull/408))

## [0.15.0] - 2026-10-27
### Bug Fixes

- recognize own-line comments written without a space ([#341](https://github.com/amfaro/jarify/pull/341)) ([#341](https://github.com/amfaro/jarify/pull/341))
- keep parentheses when writing a cast as `::` ([#342](https://github.com/amfaro/jarify/pull/342)) ([#342](https://github.com/amfaro/jarify/pull/342))
- don't put commas between wrapped window clauses ([#343](https://github.com/amfaro/jarify/pull/343)) ([#343](https://github.com/amfaro/jarify/pull/343))
- write lambdas as `lambda x: body` ([#344](https://github.com/amfaro/jarify/pull/344)) ([#344](https://github.com/amfaro/jarify/pull/344))
- keep comments after the last statement intact ([#337](https://github.com/amfaro/jarify/pull/337)) ([#337](https://github.com/amfaro/jarify/pull/337))
- keep block comment lines as written ([#338](https://github.com/amfaro/jarify/pull/338)) ([#338](https://github.com/amfaro/jarify/pull/338))
- keep comments inside WHERE and HAVING conditions ([#339](https://github.com/amfaro/jarify/pull/339)) ([#339](https://github.com/amfaro/jarify/pull/339))
- keep comments from swallowing one-line constructs ([#340](https://github.com/amfaro/jarify/pull/340)) ([#340](https://github.com/amfaro/jarify/pull/340))
- align table aliases after a bare JOIN ([#346](https://github.com/amfaro/jarify/pull/346)) ([#346](https://github.com/amfaro/jarify/pull/346))
- ignore comments when aligning aliases ([#347](https://github.com/amfaro/jarify/pull/347)) ([#347](https://github.com/amfaro/jarify/pull/347))
- keep macro statements as written ([#348](https://github.com/amfaro/jarify/pull/348)) ([#348](https://github.com/amfaro/jarify/pull/348))
- keep the joins of a FROM-first query ([#376](https://github.com/amfaro/jarify/pull/376)) ([#376](https://github.com/amfaro/jarify/pull/376))
- make set directives handle on/off options, and read normalize_join ([#364](https://github.com/amfaro/jarify/pull/364)) ([#364](https://github.com/amfaro/jarify/pull/364))
- rewrite CASE nested in a CASE that prefer-if-over-case rewrites ([#365](https://github.com/amfaro/jarify/pull/365)) ([#365](https://github.com/amfaro/jarify/pull/365))
- lay out a CASE function argument as in a SELECT list ([#366](https://github.com/amfaro/jarify/pull/366)) ([#366](https://github.com/amfaro/jarify/pull/366))
- wrap long IN value lists one value per line ([#368](https://github.com/amfaro/jarify/pull/368)) ([#368](https://github.com/amfaro/jarify/pull/368))
- wrap long window and aggregate ORDER BY lists ([#369](https://github.com/amfaro/jarify/pull/369)) ([#369](https://github.com/amfaro/jarify/pull/369))
- keep the comment above a FROM-first query ([#370](https://github.com/amfaro/jarify/pull/370)) ([#370](https://github.com/amfaro/jarify/pull/370))
- keep a comment at the end of a CTE body in the body ([#371](https://github.com/amfaro/jarify/pull/371)) ([#371](https://github.com/amfaro/jarify/pull/371))
- keep an own-line block comment on its own line ([#372](https://github.com/amfaro/jarify/pull/372)) ([#372](https://github.com/amfaro/jarify/pull/372))
- keep a comment before the first condition on its own line ([#373](https://github.com/amfaro/jarify/pull/373)) ([#373](https://github.com/amfaro/jarify/pull/373))
- keep comments after a join's table and before a CTE's paren ([#374](https://github.com/amfaro/jarify/pull/374)) ([#374](https://github.com/amfaro/jarify/pull/374))
- measure column-alias prefixes from the rendered statement ([#367](https://github.com/amfaro/jarify/pull/367)) ([#367](https://github.com/amfaro/jarify/pull/367))
- keep NOT IN, indent IN lists after OR, wrap STRING_AGG ORDER BY ([#381](https://github.com/amfaro/jarify/pull/381)) ([#381](https://github.com/amfaro/jarify/pull/381))
- lay out a multi-branch CASE in every position ([#383](https://github.com/amfaro/jarify/pull/383)) ([#383](https://github.com/amfaro/jarify/pull/383))
- keep comments after NOT, QUALIFY, ON and THEN ([#385](https://github.com/amfaro/jarify/pull/385)) ([#385](https://github.com/amfaro/jarify/pull/385))
- keep string literal line breaks in compact parts ([#387](https://github.com/amfaro/jarify/pull/387)) ([#387](https://github.com/amfaro/jarify/pull/387))
- keep a nested join, written as a parenthesized group ([#390](https://github.com/amfaro/jarify/pull/390)) ([#390](https://github.com/amfaro/jarify/pull/390))
- lay out WITH subqueries everywhere and keep own-line column comments ([#391](https://github.com/amfaro/jarify/pull/391)) ([#391](https://github.com/amfaro/jarify/pull/391))
- write a join group's first-table comment once ([#393](https://github.com/amfaro/jarify/pull/393)) ([#393](https://github.com/amfaro/jarify/pull/393))
- keep comments on operators, WINDOW, DISTINCT ON, structs and VALUES ([#395](https://github.com/amfaro/jarify/pull/395)) ([#395](https://github.com/amfaro/jarify/pull/395))
- keep ~, VALUES column names and INSERT column lists valid ([#398](https://github.com/amfaro/jarify/pull/398)) ([#398](https://github.com/amfaro/jarify/pull/398))
- let prepare-release update an existing release PR ([#400](https://github.com/amfaro/jarify/pull/400)) ([#400](https://github.com/amfaro/jarify/pull/400))
- keep column comments in place and lay out ARRAY and CASE-branch subqueries ([#401](https://github.com/amfaro/jarify/pull/401)) ([#401](https://github.com/amfaro/jarify/pull/401))

### Documentation

- describe table aliases as right-aligned ([#352](https://github.com/amfaro/jarify/pull/352)) ([#352](https://github.com/amfaro/jarify/pull/352))

### Features

- add option to keep OUTER in left and right joins ([#349](https://github.com/amfaro/jarify/pull/349)) ([#349](https://github.com/amfaro/jarify/pull/349))
- align column aliases to a visual-guide interval ([#350](https://github.com/amfaro/jarify/pull/350)) ([#350](https://github.com/amfaro/jarify/pull/350))
- allow overriding function name case ([#351](https://github.com/amfaro/jarify/pull/351)) ([#351](https://github.com/amfaro/jarify/pull/351))

## [0.14.0] - 2026-05-08
### Features

- add min column alias ([#326](https://github.com/amfaro/jarify/pull/326)) ([#326](https://github.com/amfaro/jarify/pull/326))

## [0.13.0] - 2026-05-08
### Features

- support user-global config files ([#323](https://github.com/amfaro/jarify/pull/323)) ([#323](https://github.com/amfaro/jarify/pull/323))

## [0.12.1] - 2026-05-06
### Bug Fixes

- preserve MATERIALIZED keyword on CTEs ([#319](https://github.com/amfaro/jarify/pull/319)) ([#319](https://github.com/amfaro/jarify/pull/319))

## [0.12.0] - 2026-05-06
### Features

- support `all` wildcard in disable directives ([#317](https://github.com/amfaro/jarify/pull/317)) ([#317](https://github.com/amfaro/jarify/pull/317))

## [0.11.0] - 2026-05-05
### Documentation

- clarify disable-next-line applies to entire SQL statement ([#308](https://github.com/amfaro/jarify/pull/308)) ([#308](https://github.com/amfaro/jarify/pull/308))
- remove nvarchar reference from style guide ([#309](https://github.com/amfaro/jarify/pull/309)) ([#309](https://github.com/amfaro/jarify/pull/309))

### Features

- add explicit-cross-join-needs-condition lint rule
- add cross-join-with-where-condition lint rule ([#312](https://github.com/amfaro/jarify/pull/312)) ([#312](https://github.com/amfaro/jarify/pull/312))

## [0.10.4] - 2026-05-05
### Bug Fixes

- prefer list() over ARRAY_AGG for DuckDB canonical aggregate ([#303](https://github.com/amfaro/jarify/pull/303)) ([#303](https://github.com/amfaro/jarify/pull/303))

## [0.10.3] - 2026-05-05
### Bug Fixes

- fix AS alias alignment for multi-line expressions and macro wrappers ([#300](https://github.com/amfaro/jarify/pull/300)) ([#300](https://github.com/amfaro/jarify/pull/300))

## [0.10.2] - 2026-05-04
### Bug Fixes

- align AS keyword correctly for multi-line expressions ([#297](https://github.com/amfaro/jarify/pull/297)) ([#297](https://github.com/amfaro/jarify/pull/297))

## [0.10.1] - 2026-05-04
### Bug Fixes

- align modified star formatter blocks ([#294](https://github.com/amfaro/jarify/pull/294)) ([#294](https://github.com/amfaro/jarify/pull/294))

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


