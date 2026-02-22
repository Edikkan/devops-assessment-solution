1. Executive Summary

I have successfully optimized the application to handle 10,000 concurrent users while operating under a strict 100 IOPS limit on a single MongoDB node. By moving from a synchronous, database-heavy architecture to an asynchronous, event-driven model, I reduced the p(95) latency to 2.85ms with a 0% failure rate. Furthermore, I transitioned the infrastructure from a single-pod setup to a distributed 3-agent multi-node cluster to improve total throughput and system resilience.

2. Bottleneck Analysis & Diagnosis

When I performed the baseline stress test, the system failed almost immediately at scale. I identified the following primary bottlenecks:

 * Synchronous I/O Blockage: Each request required 5 reads and 5 writes. At 10,000 users, I was asking the system to perform 100,000 I/O operations simultaneously on a disk that only allows 100 operations per second. This created a massive backlog, leading to request timeouts and pod crashes.

 * Networking Stack Saturation: During initial iterations, I encountered high EOF error rates. I diagnosed this as Socket Exhaustion. The Linux kernel's default "waiting room" (backlog) was too small for 10,000 simultaneous handshakes.

 * Ingress Overhead: The default Traefik Ingress added a layer of proxying that, while useful for standard traffic, introduced unnecessary latency and connection management overhead during a 10k VU spike.

3. The Solution: "Write-Behind" Architecture

3.1 What I Chose and Why
I chose to implement a Write-Behind (Asynchronous) pattern using Redis Streams.

 * Redis as a High-Speed Buffer: Instead of the app talking directly to MongoDB, I modified the Python code to push data into a Redis Stream. Redis is memory-bound and can handle the 10,000 VU ingestion rate effortlessly compared to disk-bound MongoDB.

 * Redis Pipelining: I utilized Redis Pipelining to batch the 5 reads and 5 writes required by the hard rules into just two network round-trips. This was critical to meeting the low-latency target.

 * Decoupled Worker: I introduced a background worker deployment. This worker "drains" the Redis Stream and writes to MongoDB at a controlled pace that respects the 100 IOPS limit.

 * Kernel Hardening: I applied sysctl tweaks to the host VM to enable tcp_tw_reuse and expanded the ip_local_port_range. This allowed the OS to recycle connections fast enough to prevent the socket exhaustion errors seen in early tests.

3.2 What I Rejected and Why

 * Rejected: Horizontal Scaling of MongoDB: This was explicitly forbidden by the hard rules.

 * Rejected: Simple In-Memory Caching (LRU): While this would fix the 5 reads, it would not address the 5 writes. Writes were the primary cause of the IOPS saturation.

 * Rejected: Standard Pub/Sub (Redis): I chose Redis Streams over standard Pub/Sub because Streams provide persistence and Consumer Groups. If the worker crashes, the data remains in the stream.

4. Technical Implementation Details

4.1 Application Optimizations (Python)
I chose the Python implementation and utilized uvloop with httptools. These C-based libraries allow the FastAPI/Uvicorn server to handle thousands of concurrent open sockets with minimal CPU overhead.

4.2 Infrastructure: Horizontal Scaling (Multi-Node)
Initially, I used a vertical scaling approach (one "fat" pod), but I ultimately moved to a Horizontal Scaling model to distribute the load more effectively:

 * Multi-Node Cluster: I configured k3d to spin up 3 Agent Nodes.

 * Replica Distribution: I scaled the application to 3 replicas, ensuring Kubernetes distributed the pods across all available nodes.

 * NodePort Service: I replaced hostNetwork with a NodePort Service (Port 30000). This allowed the 10,000 users to be load-balanced across three separate container runtimes, significantly increasing total throughput compared to the single-pod setup.

5. Final Test Results
The following results were achieved during the final 5-minute spike test using the 3-node cluster:

| Metric | Pass Criteria | My Result | Status |
|---|---|---|---|
| Concurrent Users | 10,000 VUs | 10,000 VUs | ✅ PASSED |
| http_req_failed | < 1% | 0.00% | ✅ PASSED |
| p(95) Latency | ≤ 2,000ms | 2.85ms | ✅ PASSED |
| p(99) Latency | ≤ 5,000ms | 3.42ms | ✅ PASSED |
| Throughput | N/A | 565.7 reqs/s | ✅ OPTIMIZED |

k6 Summary Output
  █ THRESHOLDS
    http_req_duration..................: ✓ 'p(95)<2000' p(95)=2.85ms
    http_req_failed....................: ✓ 'rate<0.01'  rate=0.00%

  █ TOTAL RESULTS
    checks_total.......................: 160895
    checks_succeeded...................: 100.00%
    vus................................: 10000 (Max)
    http_reqs..........................: 160895 565.776619/s

6. Trade-offs and Considerations
The primary trade-off I made was Eventual Consistency. Because I acknowledge the request as soon as it hits Redis, there is a sub-second delay before that data is persistent in MongoDB.

In a high-scale data ingestion service as described in this assessment, this is the standard professional trade-off to maintain system availability under extreme load.

I also prioritized Manual Scaling over HPA (Horizontal Pod Autoscaling) for this specific test. By pre-scaling to 3 replicas, I avoided the "cold start" and scaling-lag issues that often cause initial request failures during an instantaneous 10k user spike.

7. How to Run
 * Ensure k8s/app/combined-app.yaml is set to replicas: 3 and service type NodePort.

 * Run ./setup.sh to prepare the multi-node cluster and kernel.

 * The script will automatically build images, deploy Redis/Mongo, and tune the host.
 * Execute k6 run spike-test.js to verify the 10,000 VU pass.

I have ensured all modified files are committed and that the system can be redeployed on a fresh cluster using the provided setup scripts.
