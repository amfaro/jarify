with base as (select a, b from foo), enriched as (select base.a, bar.c from base join bar on base.id = bar.id) select enriched.a, enriched.c from enriched where enriched.a > 1
