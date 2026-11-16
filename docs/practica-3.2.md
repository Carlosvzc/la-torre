# Práctica 3.2 — CI/CD: pipeline, imagen por SHA, actualización de la flota y rollback

## Pipeline (`.github/workflows/ci.yml`, GitHub Actions)

En cada push y pull request:

1. **pruebas**: 122 pruebas del servidor (pytest), 9 de la Lambda, validación de los YAML de
   Kubernetes y `terraform fmt -check` + `terraform validate` de `infra/`.
2. **imagen** (solo si las pruebas pasan): `docker build` de `server/` con la etiqueta = **SHA corto
   del commit**. Una imagen nunca se sobrescribe: cada versión desplegada se puede rastrear al código exacto.
3. **Publicación en ECR** con OIDC (credenciales temporales, sin llaves guardadas en GitHub). Se activa
   cuando existe la variable del repositorio `AWS_ROLE_ARN`.

Captura: `docs/capturas/3.2-01-pipeline-verde.png` (los dos trabajos en verde).

**Limitación encontrada en AWS:** la cuenta pertenece a una organización del plan gratuito cuya política
(SCP) **prohíbe `iam:CreateOpenIDConnectProvider`**, así que no se puede crear el proveedor OIDC de GitHub
ni el rol que usaría el pipeline (`infra/registro.tf` lo deja detrás de `crear_oidc_github`, apagado). La
alternativa de llaves de acceso de larga duración en los secretos de GitHub se descartó a propósito (es
justo lo que el PDF recomienda evitar). Por eso la publicación en ECR se hizo **con el mismo procedimiento
del pipeline, desde la terminal**: construir, etiquetar con el SHA y subir. En una cuenta sin esa SCP basta
`-var=crear_oidc_github=true` y poner la salida `rol_github_actions` en `AWS_ROLE_ARN`.

## Despliegue de una versión nueva (medido el 16/11/2026, 20:56 UTC)

```powershell
$img = "886595576266.dkr.ecr.us-east-2.amazonaws.com/torre-server:4f65218"   # SHA del commit
docker build -t $img server; docker push $img
(Get-Content k8s\fleet-torre.yaml -Raw).Replace("IMAGEN_SERVIDOR", $img) | kubectl apply -f -
```

Antes de actualizar se asignó un servidor (`torre-fleet-9kb9l-qrpwr`) para simular una partida en curso.
50 s después de `kubectl apply`:

| GameServer | Estado | Imagen |
|---|---|---|
| torre-fleet-9kb9l-qrpwr | **Allocated** | torre-server:**67dd006** (versión anterior) |
| torre-fleet-l4nlg-7ph6v | Ready | torre-server:**4f65218** (nueva) |
| torre-fleet-l4nlg-bbfkn | Ready | torre-server:**4f65218** (nueva) |

Agones creó un GameServerSet nuevo (`l4nlg`) y **solo reemplazó los servidores libres**; el servidor
asignado siguió con la versión anterior hasta que termine su partida. Ningún jugador pierde su run por un
despliegue. Imágenes en ECR: `docs/capturas/3.2-02-imagen-sha.png`; flota: `3.2-03-flota-actualizada.png`.

## Rollback

Como cada imagen lleva el SHA de su commit y ECR conserva las anteriores, volver atrás es desplegar la
etiqueta previa:

```powershell
$img = "886595576266.dkr.ecr.us-east-2.amazonaws.com/torre-server:67dd006"   # última versión buena
(Get-Content k8s\fleet-torre.yaml -Raw).Replace("IMAGEN_SERVIDOR", $img) | kubectl apply -f -
```

Agones hace la misma sustitución gradual: los servidores libres pasan a la versión buena y las partidas en
curso terminan con la que tenían. No hace falta reconstruir nada. Para encontrar la versión anterior:
`git log --oneline` o la lista de imágenes de ECR. En un pipeline completo, el rollback sería volver a
correr el trabajo de despliegue con el SHA anterior (o un `git revert`, que genera una imagen nueva
con el código bueno).
