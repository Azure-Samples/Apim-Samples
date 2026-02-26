# Azure API Management Samples - Presentation Outline

## Meeting Format

- **Duration**: 1 hour
- **Structure**: 5 min intro | 45 min presentation & demo | 10 min Q&A

---

## Tell Them What You're Going to Tell Them (5 min)

### Gathering & Introduction (Slides 1-2)

- Welcome and introductions
- Set the stage: Today we'll cover *why* APIM Samples exists, *what* it offers, see it *in action*, and discuss *how you can use it and contribute*

### Agenda (Slide 3)

- Motivation: The APIM learning gap
- The solution: APIM Samples and its *a la carte* approach
- What's inside: Infrastructures, samples, and key features
- Live demo: Deploying infrastructure and running samples in Azure Portal
- How to use it with customers
- How you can help
- Q&A

---

## Tell Them (45 min)

### Motivation & Problem Space (Slides 4-5, ~8 min)

- **The Problem**
  - Experimenting with APIM historically falls into two extremes
  - Full landing zone accelerators can be overwhelming and more than needed
  - Isolated policy snippets require an existing APIM instance and infrastructure
  - Customers and field engineers need something in between
- **The Solution: "Just Right"**
  - APIM Samples is *neither too much nor too little*
  - Common APIM *infrastructures* paired with real-world *samples*
  - Innovative *a la carte* approach: most samples work with any infrastructure
  - Three objectives: Educate, Empower, Accelerate

### What's Inside (Slides 6-10, ~10 min)

- **5 Production-Grade Infrastructures** (Slide 6-7)
  - Simple APIM (public, fastest, ~5 min deploy, ~$1-2/hr)
  - APIM & Container Apps (APIs in ACA)
  - Front Door & APIM with Private Link (Microsoft backbone)
  - App Gateway & APIM with Private Endpoint (Standard V2)
  - App Gateway & APIM with VNet (full injection, max isolation)
  - Show architecture diagrams for each
- **8 Real-World Samples** (Slide 8)
  - General, AuthX, AuthX Pro, Azure Maps, Costing & Showback, OAuth/Spotify, Load Balancing, Secure Blob Access
  - Each sample is a Jupyter notebook with guided deployment and experimentation
- **Compatibility Matrices** (Slides 9-10)
  - Infrastructure-Sample compatibility matrix
  - Infrastructure-SKU compatibility matrix
  - Emphasize the *a la carte* flexibility

### Benefits & Differentiators (Slide 11, ~5 min)

- **Compared to other approaches** (without naming specific repos)
  - Not a full landing zone: no overhead, fast to deploy
  - Not just snippets: real, deployable infrastructure + policies
  - Modular: mix and match infrastructures and samples
  - Guided: Jupyter notebooks walk you through every step
  - Modern tooling: Codespaces/Dev Container, Bicep IaC, Developer CLI
  - Quality: OpenSSF certified, CI with pytest, code coverage
  - Cross-platform: Windows, Linux, macOS

### Live Demo (Slides 12-14, ~15 min)

- **Getting Started** (Slide 12)
  - Show Codespaces one-click launch
  - Show the Developer CLI (`start.sh` / `start.ps1`)
- **Infrastructure Deployment** (Slide 13)
  - Deploy Simple APIM infrastructure via `create.ipynb`
  - Show resources in Azure Portal
- **Sample Deployment** (Slide 14)
  - Run a sample (e.g., General or AuthX) via `create.ipynb`
  - Show APIM policies in Azure Portal
  - Make API calls and observe results
  - Demonstrate policy experimentation

### How to Use with Customers (Slide 15, ~5 min)

- Discovery and education: walk customers through architectures
- Proof of concept: deploy an infrastructure, apply customer-relevant samples
- Policy prototyping: experiment with policies before production
- Architecture comparison: show multiple infrastructures to compare approaches
- Handoff: customers can fork and continue independently

### How You Can Help (Slide 16, ~2 min)

- Star the repo and share it
- Try it and provide feedback (issues)
- Contribute new samples or improve existing ones
- Use it in customer engagements and share learnings
- Fork and adapt for specific customer scenarios

---

## Tell Them What You Told Them (Slides 17-19, ~3 min + 10 min Q&A)

### Summary (Slide 17)

- Recap the three objectives: Educate, Empower, Accelerate
- APIM Samples fills the gap between "too much" and "too little"
- 5 infrastructures, 8 samples, a la carte flexibility
- Modern, guided, cross-platform, open-source

### Resources (Slide 18)

- Repository: <https://aka.ms/apim/samples>
- APIM documentation: <https://learn.microsoft.com/azure/api-management/>
- APIM Love: <https://aka.ms/apimlove>
- Contributing guide: CONTRIBUTING.md

### Q&A (Slide 19, 10 min)

- Open floor for questions
- Share contact info and repository link
