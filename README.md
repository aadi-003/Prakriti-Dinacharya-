# 🌿 Prakriti Dinacharya

A personalized Ayurvedic-inspired wellness application that analyzes a user's **Prakriti (baseline constitution)**, **Vikriti/current state**, and **environmental conditions** to generate a personalized **Dinacharya (daily routine)**.

> **Disclaimer:** This project is an educational/wellness prototype and is not a medical diagnostic tool. Its recommendations should not replace professional medical advice.

---

## ✨ Features

### 1. Prakriti Assessment
- Questionnaire-based assessment
- Evaluates Vata, Pitta, and Kapha tendencies
- Calculates percentage distribution
- Identifies the dominant Prakriti
- Transparent rule-based scoring

### 2. Current-State / Vikriti Assessment
The application considers inputs such as:
- Heart rate
- Sleep duration
- Sleep quality
- Stress
- Energy
- Physical activity
- Mood
- Symptoms

It then estimates current tendencies and explains which rules influenced the result.

### 3. Environment Analysis
The application can consider:
- Temperature
- Humidity
- Weather
- Season

Manual environmental input is supported, with the architecture allowing future integration with location/weather APIs.

### 4. Personalized Recommendations
Recommendations can include:
- Diet guidance
- Exercise suggestions
- Sleep guidance
- Daily routine
- Pathya (supportive choices)
- Apathya (choices to avoid/limit)
- Music/raga suggestions
- Seasonal adjustments

### 5. Explainable Rule Engine
The project uses transparent rule-based logic rather than pretending to use machine learning where it is not necessary.

The system can show:
- Rules that were triggered
- Reasons behind recommendations
- Dominant/focus dosha
- Personalized outputs

---

## 🏗️ Architecture

```text
User
 │
 ▼
React + Vite Frontend
 │
 │ HTTP / JSON
 ▼
FastAPI Backend
 │
 ├── Prakriti Engine
 ├── Vikriti Engine
 ├── Environment Engine
 ├── Recommendation Engine
 ├── Rule Engine
 └── Storage
 │
 ▼
JSON Rule Files / Data