#!/usr/bin/env Rscript

suppressPackageStartupMessages({
  library(rmarkdown)
})

args <- commandArgs(trailingOnly = TRUE)

if (length(args) < 3) {
  stop("Usage: wrapper_for_knit.R <csv_path> <invoice_date> <output_pdf>", call. = FALSE)
}

csv_path    <- args[1]
invoice_date <- args[2]      # e.g. "2025-08-26"
output_pdf  <- args[3]

rmarkdown::render(
  "invoice_knit.Rmd",
  params = list(
    csv_path    = csv_path,
    invoice_date = invoice_date
  ),
  output_format = "pdf_document",
  output_file   = output_pdf,
  envir = new.env()         # keep the environment clean
)
