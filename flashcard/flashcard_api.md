# FlashcardView API

Generate educational flashcards based on a topic using Gemini. Requires user authentication via token and deducts 1 credit per generation.

---

## 🔗 Endpoint

**POST** `/api/flashcards/<user_id>/`

---

## 🔐 Authentication

Token-based. Pass `token` in the request body.

---

## 📥 Request

### Headers

```http
Content-Type: application/json
```

### Body Parameters

| Field       | Type   | Required | Description                              |
|-------------|--------|----------|------------------------------------------|
| token       | string | ✅ Yes   | User authentication token                |
| topic       | string | ✅ Yes   | Topic from which to generate flashcards  |
| language    | string | ❌ No    | Language code (default: `en`)            |

### Example Request

```json
{
  "token": "xyz12345token",
  "topic": "Photosynthesis",
  "language": "en"
}
```

---

## 📤 Response

### Success (200 OK)

```json
{
  "message": "Flashcards generated",
  "user_id": "60f82e69e13c3b001cf85a60",
  "flashcards": [
    {
      "term": "Chlorophyll",
      "definition": "A green pigment responsible for photosynthesis."
    },
    {
      "term": "Stomata",
      "definition": "Tiny pores on leaves for gas exchange."
    }
  ],
  "remaining_credits": 19
}
```

### Error Responses

#### Token Missing / Invalid

```json
{
  "error": "Token is required"
}
```

#### Token Expired

```json
{
  "error": "Token expired"
}
```

#### No Active Subscription

```json
{
  "error": "No active subscription found"
}
```

#### Subscription Expired / No Credits

```json
{
  "error": "Subscription has expired"
}
// or
{
  "error": "No remaining flashcard credits"
}
```

#### Invalid Topic or Empty Response

```json
{
  "error": "No flashcards could be generated. Try another topic or language."
}
```

---

## 🧪 Example Postman Configuration

1. Method: `POST`
2. URL: `https://your-domain.com/flashcards/<user_id>/`
3. Headers:
   - `Content-Type: application/json`
4. Body (raw JSON):
```json
{
  "token": "xyz12345token",
  "topic": "Photosynthesis",
  "language": "en"
}
```

---

## 🗣️ Supported Languages

| Code | Language     |
|------|--------------|
| en   | English      |
| ta   | Tamil        |
| hi   | Hindi        |
| ph   | Filipino     |
| fr   | French       |
| ms   | Malay        |
| etc. | ... (custom) |

---

## 📌 Notes

- The flashcards are AI-generated; ensure user reviews for correctness.
- Each generation consumes 1 subscription credit.
- API uses Gemini 2.5 Flash for accurate multilingual response generation.
