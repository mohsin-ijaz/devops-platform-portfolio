output "sql_instance_names" {
  description = "The names of the SQL instances created."
  value       = [for instance in google_sql_database_instance.sql : instance.name]
}
