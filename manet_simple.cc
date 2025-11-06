// manet_simple_fix.cc - SIN CALLBACKS PROBLEMÁTICOS
#include "ns3/core-module.h"
#include "ns3/network-module.h"
#include "ns3/internet-module.h"
#include "ns3/mobility-module.h"
#include "ns3/wifi-module.h"
#include "ns3/aodv-module.h"
#include "ns3/applications-module.h"
#include "ns3/flow-monitor-module.h"
#include "ns3/ns2-mobility-helper.h"

using namespace ns3;

NS_LOG_COMPONENT_DEFINE("ManetSimpleFix");

int main(int argc, char *argv[])
{
    // Parámetros básicos
    std::string mobilityFile = "manet_density_100_seguro.tcl";
    uint32_t numNodes = 100;
    double simulationTime = 600.0;  // 10 minutos para prueba
    uint32_t packetSize = 512;
    double interval = 2.0;

    // Parámetros de línea de comandos
    CommandLine cmd;
    cmd.AddValue("mobilityFile", "Archivo TCL de movilidad", mobilityFile);
    cmd.AddValue("numNodes", "Número de nodos", numNodes);
    cmd.AddValue("time", "Tiempo de simulación", simulationTime);
    cmd.Parse(argc, argv);

    // Logs básicos
    LogComponentEnable("UdpEchoClientApplication", LOG_LEVEL_INFO);
    LogComponentEnable("UdpEchoServerApplication", LOG_LEVEL_INFO);

    std::cout << "=== MANET SIMULATION NS-3.46 FIX ===" << std::endl;
    std::cout << "Mobility file: " << mobilityFile << std::endl;
    std::cout << "Nodes: " << numNodes << std::endl;
    std::cout << "Time: " << simulationTime << " sec" << std::endl;

    // PASO 1: Crear nodos
    NodeContainer nodes;
    nodes.Create(numNodes);
    std::cout << "✓ Created " << numNodes << " nodes" << std::endl;

    // PASO 2: Configurar movilidad
    Ns2MobilityHelper ns2 = Ns2MobilityHelper(mobilityFile);
    ns2.Install();
    std::cout << "✓ Mobility loaded" << std::endl;

    // PASO 3: WiFi Ad-hoc
    WifiHelper wifi;
    wifi.SetStandard(WIFI_STANDARD_80211b);

    WifiMacHelper mac;
    mac.SetType("ns3::AdhocWifiMac");

    YansWifiPhyHelper wifiPhy;
    YansWifiChannelHelper wifiChannel = YansWifiChannelHelper::Default();
    wifiPhy.SetChannel(wifiChannel.Create());

    wifiPhy.Set("TxPowerStart", DoubleValue(20.0));
    wifiPhy.Set("TxPowerEnd", DoubleValue(20.0));

    NetDeviceContainer devices = wifi.Install(wifiPhy, mac, nodes);
    std::cout << "✓ WiFi configured" << std::endl;

    // PASO 4: AODV routing
    AodvHelper aodv;
    InternetStackHelper stack;
    stack.SetRoutingHelper(aodv);
    stack.Install(nodes);
    std::cout << "✓ AODV installed" << std::endl;

    // PASO 5: IP addresses
    Ipv4AddressHelper address;
    address.SetBase("10.1.1.0", "255.255.255.0");
    Ipv4InterfaceContainer interfaces = address.Assign(devices);
    std::cout << "✓ IP addresses assigned" << std::endl;

    // PASO 6: Applications
    ApplicationContainer serverApps;
    ApplicationContainer clientApps;

    uint32_t numConnections = 5;
    for (uint32_t i = 0; i < numConnections && (i + numNodes/2) < numNodes; i++) {
        uint32_t serverNode = i;
        uint32_t clientNode = i + numNodes/2;
        uint16_t port = 9000 + i;

        // UDP Echo Server
        UdpEchoServerHelper echoServer(port);
        serverApps.Add(echoServer.Install(nodes.Get(serverNode)));

        // UDP Echo Client
        UdpEchoClientHelper echoClient(interfaces.GetAddress(serverNode), port);
        echoClient.SetAttribute("MaxPackets", UintegerValue(uint32_t(simulationTime/interval)));
        echoClient.SetAttribute("Interval", TimeValue(Seconds(interval)));
        echoClient.SetAttribute("PacketSize", UintegerValue(packetSize));

        clientApps.Add(echoClient.Install(nodes.Get(clientNode)));

        std::cout << "✓ Connection " << i << ": Node " << clientNode
                  << " -> Node " << serverNode << std::endl;
    }

    serverApps.Start(Seconds(1.0));
    serverApps.Stop(Seconds(simulationTime));
    clientApps.Start(Seconds(2.0));
    clientApps.Stop(Seconds(simulationTime - 1));

    // PASO 7: Flow Monitor
    FlowMonitorHelper flowmon;
    Ptr<FlowMonitor> monitor = flowmon.InstallAll();
    std::cout << "✓ Flow Monitor installed" << std::endl;

    // ELIMINAR CALLBACKS PROBLEMÁTICOS - Solo usar Flow Monitor
    std::cout << "✓ Skipping callbacks (using Flow Monitor only)" << std::endl;

    // PASO 8: Run simulation
    std::cout << "\n🚀 Starting simulation..." << std::endl;

    Simulator::Stop(Seconds(simulationTime));
    Simulator::Run();

    std::cout << "\n✅ Simulation completed!" << std::endl;

    // PASO 9: Results analysis
    std::cout << "\n=== RESULTS ANALYSIS ===" << std::endl;

    monitor->CheckForLostPackets();
    Ptr<Ipv4FlowClassifier> classifier = DynamicCast<Ipv4FlowClassifier>(flowmon.GetClassifier());
    FlowMonitor::FlowStatsContainer stats = monitor->GetFlowStats();

    uint32_t activeFlows = 0;
    double totalThroughput = 0;
    double totalDelay = 0;
    double totalJitter = 0;
    uint32_t totalTxPackets = 0;
    uint32_t totalRxPackets = 0;

    for (auto i = stats.begin(); i != stats.end(); ++i) {
        if (i->second.rxPackets == 0) continue;

        activeFlows++;
        Ipv4FlowClassifier::FiveTuple t = classifier->FindFlow(i->first);

        double throughput = i->second.rxBytes * 8.0 / simulationTime / 1000; // Kbps
        double avgDelay = i->second.delaySum.GetSeconds() / i->second.rxPackets * 1000; // ms
        double jitter = 0;
        if (i->second.rxPackets > 1) {
            jitter = i->second.jitterSum.GetSeconds() / (i->second.rxPackets - 1) * 1000; // ms
        }
        double packetLoss = 0;
        if (i->second.txPackets > 0) {
            packetLoss = (double)(i->second.txPackets - i->second.rxPackets) / i->second.txPackets * 100;
        }

        std::cout << "Flow " << activeFlows << ": "
                  << t.sourceAddress << " -> " << t.destinationAddress << std::endl;
        std::cout << "  Throughput: " << throughput << " Kbps" << std::endl;
        std::cout << "  Avg Delay: " << avgDelay << " ms" << std::endl;
        std::cout << "  Jitter: " << jitter << " ms" << std::endl;
        std::cout << "  Packet Loss: " << packetLoss << "%" << std::endl;

        totalThroughput += throughput;
        totalDelay += avgDelay;
        totalJitter += jitter;
        totalTxPackets += i->second.txPackets;
        totalRxPackets += i->second.rxPackets;
    }

    // Global metrics
    if (activeFlows > 0) {
        std::cout << "\n=== METRICAS PARA TU INVESTIGACION ===" << std::endl;
        std::cout << "Flujos activos: " << activeFlows << std::endl;
        std::cout << "Latencia promedio: " << (totalDelay/activeFlows) << " ms" << std::endl;
        std::cout << "Jitter promedio: " << (totalJitter/activeFlows) << " ms" << std::endl;
        std::cout << "Throughput total: " << totalThroughput << " Kbps" << std::endl;
        std::cout << "Perdida de paquetes: " << (double)(totalTxPackets-totalRxPackets)/totalTxPackets*100 << "%" << std::endl;
        std::cout << "Paquetes transmitidos: " << totalTxPackets << std::endl;
        std::cout << "Paquetes recibidos: " << totalRxPackets << std::endl;

        // Save results
        std::ofstream results("manet_resultados_densidad_100.txt");
        results << "# MANET Results - Urban Mobility 100 veh/hour" << std::endl;
        results << "Simulation_time_sec: " << simulationTime << std::endl;
        results << "Active_flows: " << activeFlows << std::endl;
        results << "Average_latency_ms: " << (totalDelay/activeFlows) << std::endl;
        results << "Average_jitter_ms: " << (totalJitter/activeFlows) << std::endl;
        results << "Total_throughput_Kbps: " << totalThroughput << std::endl;
        results << "Packet_loss_percent: " << (double)(totalTxPackets-totalRxPackets)/totalTxPackets*100 << std::endl;
        results << "Total_TX_packets: " << totalTxPackets << std::endl;
        results << "Total_RX_packets: " << totalRxPackets << std::endl;
        results.close();

        std::cout << "\n✅ Resultados guardados en: manet_resultados_densidad_100.txt" << std::endl;
    } else {
        std::cout << "⚠️ No active flows detected" << std::endl;
    }

    Simulator::Destroy();
    return 0;
}
