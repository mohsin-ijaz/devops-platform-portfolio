{{/*
Expand the name of the chart.
*/}}
{{- define "ssl-exporter.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "ssl-exporter.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "ssl-exporter.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "ssl-exporter.labels" -}}
helm.sh/chart: {{ include "ssl-exporter.chart" . }}
{{ include "ssl-exporter.selectorLabels" . }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- if .Values.partOf }}
app.kubernetes.io/part-of: {{ .Values.partOf }}
{{- end }}
sre.io/service: ssl-exporter
sre.io/tier: monitoring
{{- end }}

{{/*
Selector labels
*/}}
{{- define "ssl-exporter.selectorLabels" -}}
app.kubernetes.io/name: {{ include "ssl-exporter.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}
