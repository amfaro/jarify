SELECT
   _numerator_total.amount / ifnull((
    SELECT
       divisor
    FROM _variant_divisors
    WHERE context = 'numerator'
  ), 1) AS numerator_amount
  ,_denominator_total.amount / ifnull((
    SELECT
       divisor
    FROM _variant_divisors
    WHERE context = 'denominator'
  ), 1) AS denominator_amount
FROM _numerator_total
CROSS JOIN _denominator_total
;
