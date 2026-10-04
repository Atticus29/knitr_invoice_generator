#!/usr/bin/env Rscript

# Make sure pandoc is on PATH for Rscript runs (adjust the directory as needed)
Sys.setenv(PATH = paste(Sys.getenv("PATH"), "/opt/homebrew/bin", sep = ":"))
# or Sys.setenv(PATH = paste(Sys.getenv("PATH"), "/usr/local/bin", sep = ":"))

suppressPackageStartupMessages({
  library(rmarkdown)
})

args <- commandArgs(trailingOnly = TRUE)

if (length(args) < 3) {
  stop("Usage: wrapper_for_knit.R <csv_path> <invoice_date> <output_pdf> [header_title] [rate] [client] [service_period] [services_provided]", call. = FALSE)
}

csv_path    <- args[1]
invoice_date <- args[2]      # e.g. "2025-08-26"
output_pdf  <- args[3]
header_title <- if (length(args) >= 4) args[4] else "BJJ Instruction Services Invoice"
rate        <- if (length(args) >= 5) as.numeric(args[5]) else 21
client      <- if (length(args) >= 6) args[6] else "Straight Blast Gym"
service_period <- if (length(args) >= 7 && nzchar(args[7])) args[7] else format(Sys.Date(), "%Y-%m-%d")
services_provided <- if (length(args) >= 8) args[8] else "Brazilian Jiu Jitsu Instruction"

rmarkdown::render(
  "invoice_knit.Rmd",
  params = list(
    csv_path    = csv_path,
    invoice_date = invoice_date,
    header_title = header_title,
    rate        = rate,
    client      = client,
    service_period = service_period,
    services_provided = services_provided
  ),
  output_format = "pdf_document",
  output_file   = output_pdf,
  envir = new.env()         # keep the environment clean
)
