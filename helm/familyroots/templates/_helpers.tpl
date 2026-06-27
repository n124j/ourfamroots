{{/*
Return the API image
*/}}
{{- define "ourfamroots.apiImage" -}}
{{ .Values.global.imageRegistry }}/{{ .Values.image.org }}/ourfamroots/api:{{ .Values.image.tag }}
{{- end }}

{{/*
Return the worker image
*/}}
{{- define "ourfamroots.workerImage" -}}
{{ .Values.global.imageRegistry }}/{{ .Values.image.org }}/ourfamroots/worker:{{ .Values.image.tag }}
{{- end }}

{{/*
Return the frontend image
*/}}
{{- define "ourfamroots.frontendImage" -}}
{{ .Values.global.imageRegistry }}/{{ .Values.image.org }}/ourfamroots/frontend:{{ .Values.image.tag }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "ourfamroots.labels" -}}
app.kubernetes.io/name: ourfamroots
app.kubernetes.io/managed-by: Helm
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version }}
{{- end }}

{{/*
Inactive slot — the one that is NOT currently active
*/}}
{{- define "ourfamroots.inactiveSlot" -}}
{{- if eq .Values.blueGreen.activeSlot "blue" }}green{{ else }}blue{{ end }}
{{- end }}
