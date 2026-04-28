terraform {
  backend "gcs" {
    bucket  = "<TF_STATE_BUCKET>"
    prefix  = "stayinformed-task"
  }
}
