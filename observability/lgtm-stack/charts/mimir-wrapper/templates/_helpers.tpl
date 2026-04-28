{{/*
Expand the name of the chart.
*/}}
{{- define "mimir-wrapper.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "mimir-wrapper.fullname" -}}
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
{{- define "mimir-wrapper.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "mimir-wrapper.labels" -}}
helm.sh/chart: {{ include "mimir-wrapper.chart" . }}
{{ include "mimir-wrapper.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/part-of: lgtm-stack
sre.io/service: mimir
sre.io/tier: storage
{{- end }}

{{/*
Selector labels
*/}}
{{- define "mimir-wrapper.selectorLabels" -}}
app.kubernetes.io/name: {{ include "mimir-wrapper.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "mimir-wrapper.serviceAccountName" -}}
{{- if .Values.workloadIdentity.enabled }}
{{- "mimir-sa" }}
{{- else }}
{{- "default" }}
{{- end }}
{{- end }}