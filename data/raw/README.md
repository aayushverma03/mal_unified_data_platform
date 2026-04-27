# data/raw/

The 3 mock squad CSVs live here. They are committed to the repo so
reviewers can run the pipeline without first generating data.

| File | Squad | Notes |
|---|---|---|
| `cards.csv` | Cards | auth/capture lifecycle, USD float amounts (the v1 problem) |
| `transfers.csv` | Transfers | banking-rails vocabulary, AED-prefixed amount strings |
| `bill_payments.csv` | Bill Payments | scheduled-vs-executed, lowercase status, UAE billers |

To regenerate (idempotent, seed=42):

```bash
make seed
# or: python -m mal_payments.run seed
```

The three files have intentionally inconsistent schemas — different
naming conventions, different status vocabularies, different amount
representations, different timestamp conventions. Modeling realistic
schema divergence is the whole point of the exercise.
