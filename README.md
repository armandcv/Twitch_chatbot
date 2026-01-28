# Twitch Chat Desktop (Python + Tkinter)

Aplicacion de escritorio simple para leer el chat de tu canal de Twitch en local.

## Requisitos
- Python 3.11+

## Instalacion
1) Instala dependencias:
```
pip install -r requirements.txt
```

2) Crea un archivo `.env` en esta carpeta (copia `.env.example`).

3) Obtiene un User Access Token (OAuth oficial):
- Crea una app en https://dev.twitch.tv/console/apps
- Guarda tu `Client ID` y `Client Secret`
- Abre esta URL en el navegador (reemplaza CLIENT_ID):
```
https://id.twitch.tv/oauth2/authorize?client_id=CLIENT_ID&redirect_uri=http://localhost&response_type=code&scope=chat:read
```
- Copia el `code` de la URL de redireccion
- Intercambia el code por token con curl:
```
curl -X POST "https://id.twitch.tv/oauth2/token" -H "Content-Type: application/x-www-form-urlencoded" -d "client_id=CLIENT_ID&client_secret=CLIENT_SECRET&code=EL_CODE&grant_type=authorization_code&redirect_uri=http://localhost"
```

4) Completa `.env`:
```
TWITCH_TOKEN=oauth:your_access_token
TWITCH_REFRESH_TOKEN=your_refresh_token
TWITCH_CLIENT_ID=your_client_id
TWITCH_CLIENT_SECRET=your_client_secret
TWITCH_NICK=k4woks
TWITCH_CHANNEL=k4woks
TTS_RATE=180
```

## Ejecutar
```
python main.py
```

## Uso
- Conecta y muestra mensajes en tiempo real.
- El color del nick se toma del color configurado en Twitch.
- Comando TTS: `!dice <texto>` para leer el mensaje en voz alta.
- Velocidad TTS: ajusta el slider en la interfaz (o usa `TTS_RATE`).

## Crear EXE (Windows)
```
pip install pyinstaller
pyinstaller --onefile --noconsole main.py
```

El ejecutable queda en `dist/main.exe`.

## Notas
- Solo lectura de chat.
- `TWITCH_TOKEN` es obligatorio. Si agregas refresh + client id/secret, se renueva al iniciar.
- Mantener `.env` privado.
