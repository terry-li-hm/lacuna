{{- define "reg-atlas.name" -}}
reg-atlas
{{- end }}

{{- define "reg-atlas.labels" -}}
app.kubernetes.io/name: {{ include "reg-atlas.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}
