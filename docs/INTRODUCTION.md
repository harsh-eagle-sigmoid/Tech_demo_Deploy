# Unilever Procurement GPT (POC)

## 📌 Introduction

The **Unilever Procurement GPT** is an innovative AI-driven system designed to revolutionize how procurement and supply chain teams access data. In modern enterprises, vast amounts of data (Spend, Orders, Supplier Performance) are locked in databases, requiring technical SQL skills to access.

This project democratizes data access by allowing users to ask **Natural Language Questions** (e.g., "Which suppliers have high defect rates?") and receiving instant, accurate answers backed by real data.

## 🎯 Business Objectives
1.  **Democratize Data Access**: Enable non-technical users to query procurement data without SQL skills.
2.  **Speed to Insight**: Reduce time-to-answer from days to seconds.
3.  **Ensure Trust**: Guarantee that answers are based on real enterprise data (no hallucinations).

## 🚀 Technical Goals
1.  **Accuracy > 90%**: Achieve high precision on complex join queries using Few-Shot Learning.
2.  **Latency < 3s**: deliver near-instant responses using optimized SQL and caching.
3.  **Governance Layer**: Implement Real-Time Drift Detection (Vector Embeddings) and Automated Evaluation.
4.  **Modular Scalability**: Design a system where new Agents (e.g. Logistics) can be added as microservices.

## 🏗 High-Level Architecture
The system employs a **Multi-Agent Architecture**:
-   **Spend Agent**: A specialized expert in Financials (Orders, Customers, Sales).
-   **Demand Agent**: A specialized expert in Supply Chain (Inventory, Logistics, Suppliers).
-   **Guardian Layer**: A monitoring module that sits between the User and the Agents to ensure safety and correctness.

This "POC" (Proof of Concept) demonstrates that Generative AI can be safely used in enterprise environments when paired with rigorous engineering controls.
