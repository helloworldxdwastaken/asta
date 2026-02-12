# Asta WhatsApp Service (Baileys)

Lightweight WhatsApp integration for Asta using [@whiskeysockets/baileys](https://github.com/WhiskeySockets/Baileys).

## Usage

1.  **Install dependencies:**
    ```bash
    npm install
    ```

2.  **Start the service:**
    ```bash
    npm run start
    ```
    Runs on port **3001** by default.

3.  **Configure Asta Backend:**
    Ensure your `backend/.env` has:
    ```bash
    ASTA_WHATSAPP_BRIDGE_URL=http://localhost:3001
    ```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `PORT` | Service port | `3001` |
| `ASTA_API_URL` | Asta backend URL for incoming messages | `http://localhost:8010` |
