# knitr_invoice_generator
A tool meant to automate generation of contract invoices. Make with a combination of R (using knitr) and Python.

## Usage

The invoice generator can be run with optional month and year parameters:

```bash
# Generate invoice for current month
python generate_and_send_invoice.py

# Generate invoice for specific month of current year
python generate_and_send_invoice.py -m 10

# Generate invoice for specific month and year
python generate_and_send_invoice.py -m 10 -y 2024

# Using long form options
python generate_and_send_invoice.py --month 12 --year 2023
```

If no parameters are provided, the script defaults to generating an invoice for the current month.

## Configuration

Modify parameters in top section of "invoice_knit.Rmd" to suit your use case, including hourly rates (one for general teaching, one for private lessons).
Takes as input a csv file. For example:

>>>
Date_or_date_range,Hours_worked,Comments
"17 September, 2019",1.00,Q&A
"19 September, 2019",1.00,Q&A
"20 September, 2019",1.00,Q&A
"24 September, 2019",2.00,Q&A and Purple belt class coverage
"26 September, 2019",1.00,Q&A
"27 September, 2019",3.00,Coverage for Amanda and Q&A and Film Study
"27 September, 2019",1.00,Private lesson with Zach G. and Seth
>>>

Current instantiation of the code will isolate lines where the comments column contains the word, "Private", populate a separate table with just them, and charge them the separate private rate.

