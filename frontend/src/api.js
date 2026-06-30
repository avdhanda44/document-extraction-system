const jsonHeaders = {
  "Content-Type": "application/json",
};

async function readJsonResponse(response) {
  const data = await response.json().catch(() => ({}));

  if (!response.ok) {
    throw new Error(data.detail || data.message || "Request failed");
  }

  return data;
}

export async function extractDocument(file) {
  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch("/api/extract", {
    method: "POST",
    body: formData,
  });

  return readJsonResponse(response);
}

export async function saveReviewedDocument(payload) {
  const response = await fetch("/api/reviewed", {
    method: "POST",
    headers: jsonHeaders,
    body: JSON.stringify(payload),
  });

  return readJsonResponse(response);
}
