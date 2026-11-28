const maxEmailBytes = 512 * 1024;

export default {
  async email(message, env) {
    if (message.rawSize > maxEmailBytes) {
      message.setReject("Receipt exceeds the allowed size.");
      return;
    }

    const response = await fetch(env.TILLFOLD_RECEIPT_INGRESS_URL, {
      method: "POST",
      redirect: "error",
      headers: {
        Authorization: `Bearer ${env.TILLFOLD_RECEIPT_INGRESS_TOKEN}`,
        "Content-Type": "message/rfc822",
        "X-Receipt-Recipient": message.to,
        "X-Receipt-Sender": message.from,
      },
      body: message.raw,
    });

    if (!response.ok) {
      if (response.status >= 500) {
        throw new Error("Tillfold Receipt Radar is temporarily unavailable.");
      }
      message.setReject("Tillfold Receipt Radar could not accept this message.");
    }
  },
};
