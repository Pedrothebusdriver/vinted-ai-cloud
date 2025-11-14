# Hardware RFP – Vinted AI Cloud

We need a shared view of the next compute box (Pi replacement / edge node). This
Doc collects the requirements so every agent can weigh in before we shortlist a
machine.

## 1. Deployment Goals
- Keep uploads + draft processing responsive for the current testers.
- Unlock heavier models (PaddleOCR/TrOCR, FashionCLIP, NSFW detectors, Playwright
  scraper) without hopping to the cloud every time.
- Avoid a “buy twice” trap – ideally the box lasts through the next 6‑12 months
  of feature work before we architect a full scale-out.

## 2. Questions For The Team
Please drop answers/notes inline so we can converge quickly.

| Topic | Questions | Notes / Inputs |
| --- | --- | --- |
| **Workload mix** | Expected concurrent uploads? Do we plan to run scraper + OCR + compliance simultaneously? | **Current:** Overnight runs process ~60 images/hour + manual uploads. We need capacity for ~10 concurrent conversions while Playwright downloads another batch. |
| **Model roadmap** | When do we need GPU acceleration (ONNX/TensorRT, FashionCLIP finetunes)? Is CPU-only acceptable for the next phase? | **Now:** CPU OCR + CLIP embedding is fine (mobile/web upload clients already hitting the Pi). **Next 3–6 months:** plan to run FashionCLIP + PaddleOCR + NSFW detectors; GPU (RDNA3 or CUDA) would slash latency but not mandatory on day one. |
| **Memory & storage** | Minimum RAM (16 vs 32 GB)? Local storage needs (current + backlog growth)? Need spare NVMe/SATA slots? | 32 GB recommended (Playwright + inference + queue). Storage: ≥1 TB NVMe (keep `input_images`, sampler data, backups). Extra NVMe slot ideal for scratch/expansion. |
| **Power / placement** | Any noise/heat constraints? Is <25 W idle required? | Box lives in home office—low noise preferred, but small fan OK. Idle <15 W ideal; load <60 W acceptable. |
| **Networking** | Dual 2.5 GbE? Wi‑Fi 6? USB count for peripherals? Need built-in Bluetooth for the Pi camera workaround? | Dual Ethernet is nice-to-have (LAN + Tailscale). Wi-Fi 6 optional. Need 4×USB for storage, cam, misc. Bluetooth not mandatory. |
| **Virtualization** | Will we run Proxmox/VMs or just Docker/Compose? Any requirement for GPU passthrough? | Docker + systemd is fine. Keep BIOS virtualization on so we can adopt Proxmox later. GPU passthrough not required initially. |
| **Form factor** | Tiny NUC-style preferred, or can we use larger (but cooler) boxes? Wall/VESA mount needed? | NUC-style mini PC OK; VESA mount optional. Desk space is limited, so keep footprint small. |
| **Budget** | Upper limit? OK to stretch if it future-proofs us for 12+ months? | Budget ≈ £600 max. Prefer £250–£400 unless GPU gives clear win. |
| **Vendors** | Any brand preferences (Intel NUC, Minisforum, Beelink, Gigabyte BRIX, Lenovo Tiny, etc.)? Need UK/EU warranty? | Stick to vendors with UK warranty (Minisforum, Beelink, Lenovo). Avoid overseas-only support. |
| **OS** | Stick with Ubuntu 22.04 LTS? Need Windows license for dual-boot/testing? | Ubuntu 22.04 Server. No Windows license needed. |
| **Timeline** | When do we want this live? Does the Pi need to stay primary for X weeks while we migrate? | Target: hardware ordered this week, burn-in ASAP. Pi remains primary until mini PC runs 72h without incident AND the mobile/manual upload funnel is verified end-to-end. |
| **API exposure** | Will the new box expose `/api/upload` publicly (Shortcuts/web) or stay LAN-only behind VPN/Tailscale? | Need confirmation from Pete so the mobile app & docs point at the correct host/IP. If public, we must budget for reverse proxy + firewall rules. |

## 3. Candidate Classes
(Fill in as we collect data.)

| Class | Example | Pros | Cons | Fit |
| --- | --- | --- | --- | --- |
| Intel N100 mini (16 GB RAM / 500 GB NVMe) | Beelink EQ12, Morefine M6 | ~£220, 10 W TDP, silent, enough for CPU OCR/compliance, dual 2.5 GbE | CPU-only, no GPU headroom for ONNX, limited RAM ceiling | Good baseline if we expect CPU-only workloads for 6 months. |
| Ryzen 7 7840HS mini (32 GB RAM / 1 TB NVMe) | Minisforum UM780, GMKtec NucBox K8 | 8c/16t + RDNA3 iGPU, USB4, up to 64 GB RAM, can run GPU ONNX (ROCm) | £550–650, louder and higher power | Preferred if we foresee GPU-based CV/CLIP this year. |
| Ryzen 5 5600U/6600U mini (32 GB) | Lenovo ThinkCentre Tiny, Minisforum UM560 | Mid-tier price (~£350), upgradeable, moderate GPU | Not as powerful as 7840HS, but cheaper | Balanced option if budget is mid-range. |
| Jetson Orin Nano (16 GB) | NVIDIA dev kit | CUDA/TensorRT ready, low power | ARM ecosystem, limited CPU for general workloads | Only if we fully commit to GPU-only inference at the edge. |
| Used SFF (Dell/Lenovo Micro) | 8th/9th gen i7 + 32 GB | Cheap (~£200) with UK availability, easy parts | No modern iGPU, might need GPU add-on | Good as secondary/redundant node. |

## 4. Decision Criteria
- Latency target for “photo → draft” under load (<30 s end-to-end).
- Ability to run heavier models (PaddleOCR + CLIP + Playwright) simultaneously.
- 12-month runway before needing another upgrade.
- Provisioning automation support (Docker, Ansible, secrets layout).
- Physical constraints (desk space, noise). Consider staying under 1.5 kg.

## 5. Suggested Next Steps
1. Price check Intel N100 (EQ12) vs Ryzen 7840HS (UM780) in UK/EU stock.
2. Order evaluation unit (N100 if we want to validate baseline quickly).
3. Execute burn-in + provisioning plan from `docs/hardware_security.md`.
4. Log benchmarks and publish results (stress-ng, OCR timing, Playwright throughput) so we can decide if the upgrade meets our needs.
5. If N100 struggles with GPU-less tasks, move to Ryzen 7840HS or Lenovo Tiny with GPU support.
6. Document final choice + cutover plan in `docs/hardware_security.md` and update `docs/STATUS.md` once migration begins.

## 6. Codex CLI Notes (Nov 14)
- Upload + sampler queue now peak at ~10 parallel OCR/compliance jobs; plan for sustained ~150 W bursts if we lean on RDNA3 iGPU for ONNX/CLIP.
- Dual NVMe is strongly preferred so we can dedicate one drive to immutable containers/system + one to volatile `data/` (ingest, sampler cache, model weights); hot-swapping sticks will also make disaster recovery less painful.
- Ensure BIOS exposes `Resizable BAR`/`Above 4G decoding` options so the RDNA3 iGPU (if we pick Ryzen minis) can be used by ROCm/ONNX once we introduce GPU inference.
- Even if we stay CPU-only, wire at least one 2.5 GbE port into Tailscale/VLAN now—manual upload Shortcut + future reviewers will need remote access once `/api/upload` goes beyond LAN.
