# UAV Blood Delivery Network Tehran

## Paper 1: Optimizing the Location of Drone Stations for Emergency Blood Transport in Tehran

Abstract: The rapid transport of blood and medical products in emergencies is a critical challenge for urban healthcare systems, especially in megacities such as Tehran, where high population density, severe traffic congestion, and the spatial distribution of healthcare facilities can substantially increase emergency response times. This study proposes a data-driven framework for designing a drone-based blood transportation station network in Tehran. The DJI FlyCart 30 was adopted as the reference operational platform. Based on its technical specifications, an effective mission range of 12 km was assumed, corresponding to an operational service radius of 6 km for each station. Spatial data on healthcare facilities were extracted from OpenStreetMap and subsequently processed, resulting in the identification of 2,696 healthcare locations across Tehran, of which 2,674 were incorporated into the model as demand points. The facility location problem was formulated as a Set Covering Problem (SCP) to determine the minimum number of stations required to achieve complete demand coverage. The optimization results indicated that, using the preferred candidate station set, only 10 stations were sufficient to provide full coverage of all demand points. Validation analyses further confirmed that all demand locations were successfully assigned to service stations, that all missions satisfied the round-trip flight-range constraints, and that payload capacity limitations were fully respected. A Monte Carlo simulation yielded an average feasibility ratio of 0.988, demonstrating the robustness of the proposed network under simplified operational uncertainties. Sensitivity analysis also revealed that increasing the service radius from 5 km to 7 km reduced the required number of stations from 12 to 7. These findings demonstrate that cargo drones have considerable implementation potential for supporting Tehran's emergency blood supply chain in terms of both spatial coverage and operational efficiency.

Keywords: Cargo drone, Emergency blood transportation, Facility location, Set Covering Problem, Drone-based blood delivery.

```
{
  author      = {Masoud Heidari Kalahrodi and Mohammad Zia Alavi and Amir Shokri},
  email       = {masoud.heidari@ut.ac.ir, zia.alavi@ut.ac.ir, amirshokri@semnan.ac.ir},
  title       = {Optimizing the Location of Drone Stations for Emergency Blood Transport in Tehran},
  conference  = {10th International Conference on Innovation in Architectural and Urban Engineering},
  year        = {2026},
  url         = {https://www.en.symposia.ir/IUREB10},
}
```

## Paper 2: Optimal Siting of Drone Stations for Blood Transportation in Tehran Considering No-Fly Zones

Abstract: This study redesigns the facility location model for drone-based emergency blood transportation stations in Tehran by incorporating no-fly zone constraints. Spatial data on healthcare facilities, together with geographic layers representing military and security zones, governmental and political facilities, critical infrastructure, airport surroundings, and environmentally protected areas, were extracted from OpenStreetMap. To account for airport restrictions, a 3,000 m buffer was applied around actual airport features, while a 150 m buffer was assigned to point and linear features associated with the remaining restricted-area categories. During the data preprocessing stage, 2,696 healthcare facilities were initially identified. After excluding facilities located within no-fly zones, 1,545 healthcare facilities remained, of which 1,528 were considered as demand points for the analysis. The facility location problem was formulated as a Set Covering Problem (SCP) with an operational service radius of 6 km for each drone station. The optimization results showed that under flight-restriction constraints, only 9 stations were required to provide complete coverage of the remaining demand. Furthermore, all coverage, round-trip flight range, and payload capacity constraints were satisfied. The Monte Carlo simulation produced an average feasibility ratio of 0.986, indicating that the proposed network remained robust under simplified operational uncertainties. Sensitivity analysis further demonstrated that the required number of stations was 10, 9, and 7 for operational service radii of 5, 6, and 7 km, respectively. The findings indicate that incorporating no-fly zone constraints substantially reduces the effective demand network while simultaneously altering the spatial configuration of the optimal station locations compared with the baseline scenario.

Keywords: Cargo drone, Emergency blood transportation, Drone-based blood delivery, Facility location, No-fly zones.

```
{
  author      = {Masoud Heidari Kalahrodi and Mohammad Zia Alavi and Amir Shokri},
  email       = {masoud.heidari@ut.ac.ir, zia.alavi@ut.ac.ir, amirshokri@semnan.ac.ir},
  title       = {Optimal Siting of Drone Stations for Blood Transportation in Tehran Considering No-Fly Zones},
  conference  = {5th International Conference for Mechanical and Aerospace Engineers Students},
  year        = {2026},
  url         = {https://www.en.symposia.ir/MCTCD05},
}
```

## Paper 3: Analysis of the Effects of Wind Speed and Direction on the Siting of Blood-Delivery Drone Stations in Tehran

Abstract: This study investigates the combined effects of wind speed and wind direction on the design of a drone-based emergency blood transportation station network in Tehran. The analysis is based on the same preprocessed dataset used in the previous studies, which, after excluding facilities located within no-fly zones, comprises 1,545 healthcare facilities and 1,528 demand points. A scenario-based analysis was then conducted for 16 combinations of wind conditions, including four wind speeds (2, 5, 8, and 10 m/s) and four prevailing wind directions (north-to-south, south-to-north, east-to-west, and west-to-east). In the proposed model, wind was not treated solely as a temporal factor affecting flight duration; instead, a wind-dependent effective distance metric was introduced, allowing wind conditions to directly influence service coverage and, consequently, station selection. The results showed that, under the baseline no-wind scenario, complete demand coverage could be achieved with nine stations. However, in seven of the sixteen wind scenarios, the required number of stations increased to ten. Moreover, even when the total number of stations remained unchanged, the composition of the selected station locations changed substantially. These findings demonstrate that, in the design of urban drone networks, wind direction is as influential as wind speed, and neglecting its effects may lead to overly optimistic estimates of network coverage capability.

Keywords: Emergency blood transportation, Drone-based blood delivery, No-fly zones, Wind effects.

```
{
  author      = {Masoud Heidari Kalahrodi and Mohammad Zia Alavi and Amir Shokri},
  email       = {masoud.heidari@ut.ac.ir, zia.alavi@ut.ac.ir, amirshokri@semnan.ac.ir},
  title       = {Analysis of the Effects of Wind Speed and Direction on the Siting of Blood-Delivery Drone Stations in Tehran},
  conference  = {10th International Conference on Technology Development in Mechanical and Aerospace Engineering},
  year        = {2026},
  url         = {https://www.en.symposia.ir/METEC10},
}
```
## Paper 4: Analysis of the Impact of Ambient Temperature on the Effective Flight Range and Optimal Siting of Drone Stations for Blood Transportation in Tehran

Abstract: This study investigates the impact of ambient temperature on battery performance and, consequently, on the operational range of a drone-based emergency blood transportation network in Tehran. The analysis is based on the same preprocessed dataset used in previous versions of this research, in which healthcare facilities located within no-fly zones were excluded before designing the drone station network. The primary contribution of this study is that temperature is not treated merely as a qualitative consideration or an auxiliary operational constraint; instead, it is explicitly incorporated into the optimization model through a battery performance coefficient that directly affects service coverage, the effective operational radius, and the round-trip mission range. To evaluate the influence of temperature, five environmental scenarios (S1–S5) were defined to represent optimal, moderately hot, extremely hot, cold, and extremely cold conditions. Under the baseline scenario (S1), with a battery performance coefficient of 1.00, the network achieved complete demand coverage using nine stations. The results indicate that, although the number of required stations remained unchanged in the moderately hot scenario (S2), the configuration of the selected stations changed substantially. In both the extremely hot (S3) and cold (S4) scenarios, the required number of stations increased to 10, while in the extremely cold scenario (S5), 11 stations were necessary to maintain complete coverage. These findings demonstrate that temperature-induced battery degradation not only reduces the effective flight range but can also alter the optimal facility location solution. Therefore, the design of drone networks for critical healthcare missions, such as emergency blood transportation, should explicitly account for temperature effects through a scenario-based planning framework.

Keywords: Cargo drone, Emergency blood transportation, Drone-based blood delivery, No-fly zones, Battery performance, Ambient temperature.

```
{
  author      = {Masoud Heidari Kalahrodi and Mohammad Zia Alavi and Amir Shokri},
  email       = {masoud.heidari@ut.ac.ir, zia.alavi@ut.ac.ir, amirshokri@semnan.ac.ir},
  title       = {Analysis of the Impact of Ambient Temperature on the Effective Flight Range and Optimal Siting of Drone Stations for Blood Transportation in Tehran},
  conference  = {4th International Congress of Scientific and Technological Development of Civil Engineering Students of Iran},
  year        = {2026},
  url         = {https://www.en.symposia.ir/CIVILCDSTS04},
}
```
## Paper 5: Wind-Energy-Aware Siting and No-Fly-Zone-Safe Routing of Drone Stations for Emergency Blood Transportation in Tehran

Abstract: Straight-line distance often substantially overestimates the operational coverage of urban drone networks because it does not ensure that flight paths avoid no-fly zones or account for the directional effects of wind on asymmetric, loaded outbound and light return missions. This study presents an integrated framework for siting emergency blood-delivery drone stations in Tehran by explicitly constructing obstacle-safe routes and evaluating round-trip, wind-dependent energy consumption. OpenStreetMap data identified 2,696 healthcare facilities and 2,674 demand points. Among these, 1,146 demand points were located within restricted zones. They were retained in the accessibility audit as requiring special authorization or a ground handoff, while 1,528 destinations remained potentially eligible for direct drone service. The airspace was discretized into a 100 m grid using UTM coordinates, and a 100 m safety clearance was applied around no-fly polygons. A Dijkstra algorithm was implemented to minimize edge-level round-trip energy for loaded outbound and light return legs. Energy rates were calibrated using official DJI FlyCart 30 dual-battery ranges, with a 20% battery reserve and a 4% takeoff-and-landing allowance enforced. A set-covering model was subsequently used to minimize the number of stations. Under calm conditions, a straight-line model selected six stations and appeared to cover all 1,517 grid-connectable destinations; however, 1,186 assignments (78.2%) intersected at least one no-fly zone. The proposed model selected 21 stations, covered 1,449 of the 1,528 potentially drone-eligible destinations (94.8%), and produced zero intersections across all reported routes. The mean safe-route length was 3.11 km, the mean safe-path-to-straight-line ratio was 1.32, and mean total battery use was 32.1%. Wind scenarios at 5 m/s required 21–22 stations, while 10 m/s scenarios required 24–25 stations. Sensitivity analysis over grid resolutions of 75, 100, and 150 m and battery reserves of 15%, 20%, and 25% yielded 20–24 stations. These results demonstrate that explicit modeling of no-fly-zone geometry and directional wind energy significantly alters both network connectivity and optimal station siting, indicating that straight-line coverage is inadequate for operational planning in constrained urban airspace.

Keywords: Emergency blood transportation; Cargo drone; No-fly zones; Energy-aware routing; Wind effects; Facility location; Tehran.

```
{
  author      = {Masoud Heidari Kalahrodi and Mohammad Zia Alavi and Amir Shokri},
  email       = {masoud.heidari@ut.ac.ir, zia.alavi@ut.ac.ir, amirshokri@semnan.ac.ir},
  title       = {Wind-Energy-Aware Siting and No-Fly-Zone-Safe Routing of Drone Stations for Emergency Blood Transportation in Tehran},
  conference  = {10th International Conference on Information Technology Engineering, Computer Sciences and Telecommunication of Iran},
  year        = {2026},
  url         = {https://www.en.symposia.ir/ITCT10},
}
```
