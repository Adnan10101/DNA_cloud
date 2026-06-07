{{/*
Common labels applied to every resource in this chart.
*/}}
{{- define "homelab-db.labels" -}}
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version }}
app.kubernetes.io/name: {{ .Chart.Name }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels scoped to a specific component.
Usage: include "homelab-db.selectorLabels" (dict "root" . "component" "pgadmin")
*/}}
{{- define "homelab-db.selectorLabels" -}}
app.kubernetes.io/name: {{ .root.Chart.Name }}
app.kubernetes.io/instance: {{ .root.Release.Name }}
app.kubernetes.io/component: {{ .component }}
{{- end }}
