from __future__ import annotations

from typing import Iterable


COLOR_CLASSES = {
    "OK": "status-ok",
    "CAUTION": "status-caution",
    "WARNING": "status-warning",
    "UNKNOWN": "status-unknown",
}


def page_wrapper(
    title: str,
    body: str,
    mode_info: dict,
    active_tab: str = "airfields",
    prefix: str = "",
) -> str:
    return f"""
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <meta name="base-path" content="{prefix}" />
  <title>{title}</title>
  <script async src="https://www.googletagmanager.com/gtag/js?id=G-M3MJGMR2GD"></script>
  <script>
    window.dataLayer = window.dataLayer || [];
    function gtag(){{dataLayer.push(arguments);}}
    gtag('js', new Date());
    gtag('config', 'G-M3MJGMR2GD');
  </script>
  <link rel="stylesheet" href="{prefix}assets/style.css" />
</head>
<body>
  <header>
    <h1>METAR.oncloud.africa</h1>
    <p class="disclaimer">Training/augmentation only. Not an official briefing source.</p>
    <nav>
      <a class="{_active(active_tab, 'airfields')}" href="{prefix}index.html">Airfields</a>
      <a class="{_active(active_tab, 'routes')}" href="{prefix}routes.html">Routes</a>
      <a class="{_active(active_tab, 'tools')}" href="{prefix}tools/index.html">Tools</a>
    </nav>
    <div class="mode-row">
      <span class="mode-banner {mode_info['class']}">
        <span class="icon">●</span>{mode_info['label']} — {mode_info['text']}
      </span>
      <label class="mode-select">Mode
        <select disabled>
          <option selected>{mode_info['label']}</option>
          <option>LIVE_BETA</option>
        </select>
      </label>
    </div>
  </header>
  <main class="container">
    {body}
  </main>
  <footer>
    <p>Training/augmentation only. Verify with SAWS/ATC/AIP/NOTAM office and POH/AFM.</p>
    <p>Computed values are approximations.</p>
  </footer>
  <script src="{prefix}assets/app.js"></script>
</body>
</html>
"""


def _active(active: str, tab: str) -> str:
    return "active" if active == tab else ""


def _format_variable_wind(variable: dict | None) -> str:
    if not variable:
        return "--"
    return f"{variable.get('from', '--')}°–{variable.get('to', '--')}°"


def _format_cloud_layers(layers: list[dict]) -> str:
    if not layers:
        return "--"
    return ", ".join(
        f"{layer['cover']} {layer['base_ft']} ft"
        for layer in layers
        if layer.get("cover") and layer.get("base_ft") is not None
    )


def _format_ceiling(ceiling_ft: int | None, layers: list[dict]) -> str:
    if ceiling_ft is not None:
        return f"{ceiling_ft} ft"
    if layers:
        return "None (no BKN/OVC)"
    return "--"


def airfield_cards(airfields: Iterable[dict]) -> str:
    cards = []
    for airfield in airfields:
        flags = airfield["computed"]["flags"]
        badge = flags[0] if flags else "LOW_RISK"
        top_flags = ", ".join(flags[:2]) if flags else "LOW_RISK"
        status = airfield["computed"]["severity"]["level"]
        status_class = COLOR_CLASSES.get(status, "status-unknown")
        night_badge = "Night-ready" if airfield["night_ready"] else "Night limited"
        workload = airfield["computed"]["workload"]
        stability = airfield["computed"]["stability"]
        cards.append(
            f"""
            <div class="card" data-ident="{airfield['ident']}">
              <div class="card-header">
                <h3>{airfield['ident']} — {airfield.get('name','')}</h3>
                <span class="pill {status_class}"><span class="icon">●</span>{status}</span>
              </div>
              <p><strong>Updated:</strong> {airfield['metar']['observed_time_utc'] or 'Unknown'}
                ({airfield['metar']['source']})</p>
              <p>Wind: {airfield['metar']['wind_dir_deg'] or 'VRB'}°
                {airfield['metar']['wind_speed_kt'] or '--'} kt</p>
              <p>QNH: {airfield['metar']['qnh_hpa'] or '--'} hPa</p>
              <p>Temp/Dew: {airfield['metar']['temp_c'] or '--'}°C /
                {airfield['metar']['dewpoint_c'] or '--'}°C</p>
              <p>DA: {airfield['computed']['density_altitude']['da_ft'] or '--'} ft</p>
              <p>Workload: {workload['category']} ({workload['score']})</p>
              <p>Stability: {stability['category']} ({stability['score']})</p>
              <div class="badge-row">
                <span class="badge">{badge}</span>
                <span class="badge night">{night_badge}</span>
              </div>
              <p><strong>Top warnings:</strong> {top_flags}</p>
              <p><a href="airfield/{airfield['ident']}.html">Open briefing</a></p>
            </div>
            """
        )
    return "\n".join(cards)


def route_cards(routes: Iterable[dict]) -> str:
    cards = []
    for route in routes:
        status = route["summary"]["severity"]["level"]
        status_class = COLOR_CLASSES.get(status, "status-unknown")
        cards.append(
            f"""
            <div class="card" data-route="{route['route_id']}">
              <div class="card-header">
                <h3>{route['route_id']}</h3>
                <span class="pill {status_class}"><span class="icon">●</span>{status}</span>
              </div>
              <p>{route['dep']} → {route['dest']}</p>
              <p>Corridor: {route['corridor_nm']} NM</p>
              <p>Levels: {', '.join(str(level) for level in route['cruise_levels_ft'])}</p>
              <p><a href="route/{route['route_id']}.html">Open route pack</a></p>
            </div>
            """
        )
    return "\n".join(cards)


def render_home(airfields: list[dict], profile_name: str, mode_info: dict) -> str:
    body = f"""
    <section class="summary">
      <h2>Airfields overview</h2>
      <p>Profile: {profile_name} — thresholds and flags are training aids only.</p>
      <input id="airfield-search" type="search" placeholder="Search airfields..." />
    </section>
    <section class="grid">{airfield_cards(airfields)}</section>
    """
    return page_wrapper(
        "METAR.oncloud.africa — Airfields",
        body,
        mode_info,
        active_tab="airfields",
        prefix="",
    )


def render_routes_index(routes: list[dict], mode_info: dict) -> str:
    body = f"""
    <section class="summary">
      <h2>ATPL route packs</h2>
      <p>Generated from sample data. Each pack includes METAR/TAF, NOTAM highlights,
        upper winds, SIGMET/AIRMET, and SIGWX charts.</p>
      <input id="route-search" type="search" placeholder="Search routes..." />
    </section>
    <section class="grid">{route_cards(routes)}</section>
    """
    return page_wrapper(
        "METAR.oncloud.africa — Routes",
        body,
        mode_info,
        active_tab="routes",
        prefix="",
    )


def render_airfield_page(airfield: dict, mode_info: dict) -> str:
    metar = airfield["metar"]
    taf = airfield["taf"]
    cloud_layers = _format_cloud_layers(metar.get("cloud_layers", []))
    ceiling = _format_ceiling(metar.get("ceiling_ft"), metar.get("cloud_layers", []))
    variable_wind = _format_variable_wind(metar.get("variable_wind"))
    runways = "".join(
        (
            "<tr>"
            f"<td>{c['runway']}</td>"
            f"<td>{c['headwind_kt']}</td>"
            f"<td>{c['crosswind_kt']} ({c['crosswind_side']})</td>"
            f"<td>{c['tailwind_kt']}</td>"
            "</tr>"
        )
        for c in airfield["computed"]["wind_components_per_runway"]
    )
    flags = airfield["computed"]["flags"] or ["LOW_RISK"]
    explanations = airfield["computed"]["flag_explanations"]
    flags_html = "".join(
        f"<details><summary>{flag}</summary><pre>{explanations.get(flag, {})}</pre></details>"
        for flag in flags
    )
    trend_data = airfield["computed"]["trends"]
    night = airfield["night_ops"]
    changes = airfield["computed"]["changes"]
    taf_expiry = airfield["computed"]["taf_time_to_expiry"]
    sun = airfield["computed"]["sun"]
    workload = airfield["computed"]["workload"]
    stability = airfield["computed"]["stability"]

    body = f"""
    <section class="summary">
      <h2>{airfield['ident']} — {airfield.get('name','')}</h2>
      <p><strong>Raw METAR:</strong> {metar['raw']}</p>
      <p>Observed: {metar['observed_time_utc'] or 'Unknown'} ({metar['source']})</p>
      <p>Data source: {metar.get('source_detail', 'Unknown')}</p>
      <p>Fetch time: {metar.get('fetch_time_utc', '--')} |
        Latency: {metar.get('latency_min', '--')} min</p>
    </section>

    <section class="section">
      <h3>Decoded METAR</h3>
      <table class="table">
        <tr><th>Wind</th>
          <td>{metar['wind_dir_deg'] or 'VRB'}° {metar['wind_speed_kt'] or '--'} kt</td></tr>
        <tr><th>Gust</th><td>{metar['gust_kt'] or '--'} kt</td></tr>
        <tr><th>Variable wind</th><td>{variable_wind}</td></tr>
        <tr><th>Visibility</th><td>{metar['visibility_m'] or '--'} m</td></tr>
        <tr><th>Weather</th><td>{', '.join(metar['weather_codes']) or '--'}</td></tr>
        <tr><th>Clouds</th><td>{cloud_layers}</td></tr>
        <tr><th>Ceiling</th><td>{ceiling}</td></tr>
        <tr><th>Temperature</th><td>{metar['temp_c'] or '--'} °C</td></tr>
        <tr><th>Dewpoint</th><td>{metar['dewpoint_c'] or '--'} °C</td></tr>
        <tr><th>QNH</th><td>{metar['qnh_hpa'] or '--'} hPa</td></tr>
      </table>
    </section>

    <section class="section">
      <h3>TAF summary</h3>
      <p><strong>Raw TAF:</strong> {taf['raw']}</p>
      <p>Valid: {taf['summary']['valid_from']} → {taf['summary']['valid_to']}</p>
      <p>Key changes: {', '.join(taf['summary']['key_changes']) or 'None'}</p>
      <p>Time to TAF expiry:
        <span class="urgency-{taf_expiry['urgency']}">{taf_expiry['hours'] or '--'} hours</span></p>
    </section>

    <section class="section">
      <h3>Runway wind components</h3>
      <p class="note">Why it matters: Crosswind, tailwind, and gust spread affect handling and
        performance. Headwind is generally helpful but not a limit.</p>
      <table class="table">
        <tr><th>Runway</th><th>Headwind (kt)</th><th>Crosswind (kt)</th><th>Tailwind (kt)</th></tr>
        {runways}
      </table>
    </section>

    <section class="section">
      <h3>Night operations</h3>
      <ul>
        <li>Night ops allowed: {night['night_ops_allowed']}</li>
        <li>Lighting: RWY edge {night['lighting']['runway_edge']},
          threshold {night['lighting']['threshold']}, taxiway {night['lighting']['taxiway']},
          apron {night['lighting']['apron']}</li>
        <li>PPR required: {night['ppr_required']}</li>
        <li>Ops hours: {night['ops_hours']}</li>
        <li>Notes: {night['notes']}</li>
      </ul>
    </section>

    <section class="section">
      <h3>Airspace & Circuit</h3>
      <ul>
        <li>CTR: {airfield['airspace_context']['ctr']}</li>
        <li>TMA: {airfield['airspace_context']['tma']}</li>
        <li>Class: {airfield['airspace_context'].get('class', '--')}</li>
        <li>Circuit: {airfield['circuit']['direction']} /
          {airfield['circuit']['height_ft_agl']} ft AGL</li>
        <li>Noise abatement: {airfield.get('noise_abatement_notes', '--')}</li>
      </ul>
    </section>

    <section class="section">
      <h3>Time awareness</h3>
      <p>Sunrise: {sun['sunrise'] or '--'} | Sunset: {sun['sunset'] or '--'}</p>
      <p>Civil twilight: {sun['civil_twilight_start'] or '--'} →
        {sun['civil_twilight_end'] or '--'}</p>
      <div class="timeline">
        <span>Now</span>
        <span>TAF ends {taf_expiry['hours'] or '--'}h</span>
        <span>Sunset {sun['sunset'] or '--'}</span>
      </div>
    </section>

    <section class="section">
      <h3>What changed since last update</h3>
      <p>{changes['summary']}</p>
      <pre>{changes['details']}</pre>
    </section>

    <section class="section">
      <h3>Workload today</h3>
      <p>{workload['category']} ({workload['score']}) — Top contributors:
        {', '.join(workload['top_contributors'])}</p>
    </section>

    <section class="section">
      <h3>Stability score</h3>
      <p>{stability['category']} ({stability['score']}) — Drivers:
        {', '.join(stability['drivers'])}</p>
    </section>

    <section class="section">
      <h3>Trends</h3>
      <div class="trend" data-trend='{trend_data}'></div>
      <div class="sparkline" data-spark='{trend_data["wind_speed"]}'></div>
      <div class="sparkline" data-spark='{trend_data["qnh"]}'></div>
      <div class="sparkline" data-spark='{trend_data["temp"]}'></div>
      <div class="sparkline" data-spark='{trend_data["dewpoint"]}'></div>
    </section>

    <section class="section">
      <h3>Flags</h3>
      <div class="flag-list">{flags_html}</div>
    </section>
    """
    return page_wrapper(
        f"{airfield['ident']} briefing",
        body,
        mode_info,
        active_tab="airfields",
        prefix="../",
    )


def render_route_page(route: dict, sigwx_paths: dict, mode_info: dict) -> str:
    metar_rows = "".join(
        (
            "<tr>"
            f"<td>{item['ident']}</td>"
            f"<td>{item['metar']['raw']}</td>"
            f"<td>{item['taf']['raw']}</td>"
            "</tr>"
        )
        for item in route["airfields"]
    )
    upper_rows = "".join(
        (
            "<tr>"
            f"<td>{level['level_ft']}</td>"
            f"<td>{level['wind_dir_deg']}/{level['wind_speed_kt']} kt</td>"
            f"<td>{level['temp_c']} °C</td>"
            f"<td>{level['headwind_kt']}</td>"
            f"<td>{level['ground_speed_kt']}</td>"
            "</tr>"
        )
        for level in route["upper_winds"]
    )
    sigmet_cards = "".join(
        f"<div class='card'><p>{line}</p></div>" for line in route["sigmet_lines"]
    )
    notam_cards = "".join(
        f"<div class='card'><strong>{ident}</strong><p>{'<br/>'.join(lines)}</p></div>"
        for ident, lines in route["notams"].items()
    )

    body = f"""
    <section class="summary">
      <h2>{route['route_id']} — {route['dep']} → {route['dest']}</h2>
      <p>Track: {route['track_deg'] or 'Unknown'}° | Corridor: {route['corridor_nm']} NM</p>
      <div class="badge-row">
        {''.join(f'<span class="badge">{flag}</span>' for flag in route['summary']['flags'])}
      </div>
      <p>Workload: {route['summary']['workload']['category']}
        ({route['summary']['workload']['score']})</p>
      <p>Stability: {route['summary']['stability']['category']}
        ({route['summary']['stability']['score']})</p>
    </section>

    <section class="section">
      <h3>Weather summary</h3>
      <table class="table">
        <tr><th>Aerodrome</th><th>METAR</th><th>TAF</th></tr>
        {metar_rows}
      </table>
      <p>TAF expiry: Dep {route['taf_time_to_expiry']['dep']['hours'] or '--'}h |
        Dest {route['taf_time_to_expiry']['dest']['hours'] or '--'}h</p>
    </section>

    <section class="section">
      <h3>NOTAM highlights</h3>
      <div class="grid">{notam_cards}</div>
    </section>

    <section class="section">
      <h3>Upper winds & temperatures</h3>
      <table class="table">
        <tr><th>Level (ft)</th><th>Wind</th><th>Temp</th><th>Headwind (kt)</th>
          <th>Ground speed (kt)</th></tr>
        {upper_rows}
      </table>
      <p>Freezing level estimate: {route['freezing_level_ft'] or 'Unknown'} ft</p>
    </section>

    <section class="section">
      <h3>SIGMET / AIRMET</h3>
      <div class="grid">{sigmet_cards}</div>
      <p>Time to SIGMET expiry: {route['sigmet_time_to_expiry']['hours'] or '--'}h</p>
    </section>

    <section class="section">
      <h3>SIGWX charts</h3>
      <div class="grid">
        <div class="card"><img src="../assets/{sigwx_paths['low']}"
          alt="Low-level SIGWX sample" /></div>
        <div class="card"><img src="../assets/{sigwx_paths['high']}"
          alt="High-level SIGWX sample" /></div>
      </div>
      <p class="note">For training reference only.</p>
    </section>
    """
    return page_wrapper(
        f"{route['route_id']} route pack",
        body,
        mode_info,
        active_tab="routes",
        prefix="../",
    )


def render_tools_index(mode_info: dict) -> str:
    body = """
    <section class="summary">
      <h2>Training Tools</h2>
      <p>Interactive calculators for ISA, density altitude, TAS, hypoxia, pressurisation,
        and scenario building.</p>
    </section>
    <section class="grid">
      <div class="card"><h3>ISA</h3><p><a href="isa.html">Open tool</a></p></div>
      <div class="card"><h3>Altimetry</h3><p><a href="altimetry.html">Open tool</a></p></div>
      <div class="card"><h3>Density Altitude</h3>
        <p><a href="density-altitude.html">Open tool</a></p></div>
      <div class="card"><h3>IAS → TAS</h3><p><a href="tas.html">Open tool</a></p></div>
      <div class="card"><h3>Gas Laws & Hypoxia</h3><p><a href="hypoxia.html">Open tool</a></p></div>
      <div class="card"><h3>Pressurisation</h3>
        <p><a href="pressurisation.html">Open tool</a></p></div>
      <div class="card"><h3>Aircraft Reference</h3>
        <p><a href="aircraft.html">Open tool</a></p></div>
      <div class="card"><h3>Scenario Builder</h3><p><a href="scenario.html">Open tool</a></p></div>
    </section>
    """
    return page_wrapper(
        "METAR.oncloud.africa — Tools",
        body,
        mode_info,
        active_tab="tools",
        prefix="../",
    )


def render_tool_page(title: str, content: str, mode_info: dict) -> str:
    body = f"""
    <section class="summary">
      <h2>{title}</h2>
      <p class="note">Training-only, simplified models. Always verify with official sources
        and POH/AFM.</p>
    </section>
    <section class="section">{content}</section>
    """
    return page_wrapper(f"{title} — Tools", body, mode_info, active_tab="tools", prefix="../")
