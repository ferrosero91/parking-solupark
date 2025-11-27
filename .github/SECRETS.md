# 🔐 Configuración de Secrets en GitHub

Para que los workflows de CI/CD funcionen correctamente, necesitas configurar los siguientes secrets en tu repositorio de GitHub.

## 📍 Cómo agregar secrets

1. Ve a tu repositorio en GitHub
2. Click en **Settings** → **Secrets and variables** → **Actions**
3. Click en **New repository secret**
4. Agrega cada secret con su nombre y valor

---

## 🚀 Secrets para Deploy en Render

### `RENDER_API_KEY`
- **Descripción**: API Key de Render para deploys automáticos
- **Cómo obtenerlo**: 
  1. Ve a [Render Dashboard](https://dashboard.render.com/)
  2. Click en tu avatar → Account Settings
  3. API Keys → Create API Key
- **Ejemplo**: `rnd_xxxxxxxxxxxxxxxxxxxxx`

### `RENDER_SERVICE_ID`
- **Descripción**: ID del servicio web en Render (producción)
- **Cómo obtenerlo**:
  1. Ve a tu servicio en Render
  2. La URL será: `https://dashboard.render.com/web/srv-XXXXXX`
  3. El ID es la parte después de `srv-`
- **Ejemplo**: `srv-abc123def456`

### `RENDER_STAGING_SERVICE_ID`
- **Descripción**: ID del servicio de staging en Render
- **Cómo obtenerlo**: Igual que el anterior, pero para el servicio de staging
- **Ejemplo**: `srv-xyz789uvw012`

### `RENDER_APP_URL`
- **Descripción**: URL de tu aplicación en producción
- **Ejemplo**: `https://tu-app.onrender.com`

### `STAGING_URL`
- **Descripción**: URL de tu aplicación en staging
- **Ejemplo**: `https://tu-app-staging.onrender.com`

---

## 🖥️ Secrets para Deploy en VPS (Opcional)

### `VPS_HOST`
- **Descripción**: IP o dominio de tu VPS
- **Ejemplo**: `192.168.1.100` o `vps.tudominio.com`

### `VPS_USERNAME`
- **Descripción**: Usuario SSH del VPS
- **Ejemplo**: `ubuntu` o `root`

### `VPS_SSH_KEY`
- **Descripción**: Clave privada SSH para conectar al VPS
- **Cómo obtenerlo**:
  ```bash
  # En tu máquina local
  ssh-keygen -t ed25519 -C "github-actions"
  # Copia el contenido de la clave privada
  cat ~/.ssh/id_ed25519
  # Copia la clave pública al VPS
  ssh-copy-id usuario@vps-ip
  ```
- **Formato**: Copia todo el contenido del archivo, incluyendo:
  ```
  -----BEGIN OPENSSH PRIVATE KEY-----
  ...contenido...
  -----END OPENSSH PRIVATE KEY-----
  ```

### `VPS_PORT`
- **Descripción**: Puerto SSH del VPS
- **Ejemplo**: `22` (por defecto)

### `VPS_URL`
- **Descripción**: URL de tu aplicación en el VPS
- **Ejemplo**: `https://tudominio.com`

---

## 🗄️ Secrets de Base de Datos (Opcional para backups)

### `DATABASE_HOST`
- **Descripción**: Host de la base de datos PostgreSQL
- **Ejemplo**: `postgres.render.com`

### `DATABASE_NAME`
- **Descripción**: Nombre de la base de datos
- **Ejemplo**: `parking_system_db`

### `DATABASE_USER`
- **Descripción**: Usuario de la base de datos
- **Ejemplo**: `parking_user`

### `DATABASE_PASSWORD`
- **Descripción**: Contraseña de la base de datos
- **Ejemplo**: `contraseña-segura-aqui`

---

## ☁️ Secrets para AWS S3 (Opcional para backups)

### `AWS_ACCESS_KEY_ID`
- **Descripción**: Access Key ID de AWS
- **Cómo obtenerlo**: AWS Console → IAM → Users → Security credentials

### `AWS_SECRET_ACCESS_KEY`
- **Descripción**: Secret Access Key de AWS
- **Cómo obtenerlo**: Se muestra solo al crear el Access Key

---

## ✅ Verificación de Secrets

Después de agregar los secrets, verifica que estén configurados:

1. Ve a **Settings** → **Secrets and variables** → **Actions**
2. Deberías ver una lista como esta:

```
✓ RENDER_API_KEY
✓ RENDER_SERVICE_ID
✓ RENDER_STAGING_SERVICE_ID
✓ RENDER_APP_URL
✓ STAGING_URL
```

---

## 🔒 Seguridad

- ❌ **NUNCA** compartas estos secrets públicamente
- ❌ **NUNCA** los commits en el repositorio
- ✅ Usa secrets diferentes para staging y producción
- ✅ Rota los secrets periódicamente
- ✅ Usa permisos mínimos necesarios

---

## 🧪 Probar los Workflows

Una vez configurados los secrets:

1. Haz un commit y push a `develop` para probar staging
2. Haz un commit y push a `main` para probar producción
3. Revisa los logs en la pestaña **Actions** de GitHub

---

## 🆘 Troubleshooting

### Error: "Secret not found"
- Verifica que el nombre del secret sea exactamente igual (case-sensitive)
- Asegúrate de que el secret esté en el repositorio correcto

### Error: "Invalid API key"
- Regenera el API key en Render
- Actualiza el secret en GitHub

### Error: "Permission denied (publickey)"
- Verifica que la clave SSH esté correctamente copiada
- Asegúrate de que la clave pública esté en el VPS (`~/.ssh/authorized_keys`)

---

## 📚 Referencias

- [GitHub Secrets Documentation](https://docs.github.com/en/actions/security-guides/encrypted-secrets)
- [Render API Documentation](https://render.com/docs/api)
- [SSH Key Generation](https://docs.github.com/en/authentication/connecting-to-github-with-ssh/generating-a-new-ssh-key-and-adding-it-to-the-ssh-agent)
