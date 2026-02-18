# webapp for cotc
plan 

This will be whats put on the vm,

The aggregator needs to recieve this json (example),

{
  "status": "success",
  "timestamp": "2026-02-18T13:19:55.414480",
  "count": 46,
  "data": [
    {
      "name": "system_info.hostname",
      "value": "Junior",
      "collector_type": "laptop",
      "timestamp": "2026-02-18T13:19:29.399974",
      "unit": null
    },
    {
      "name": "system_info.os",
      "value": "Linux",
      "collector_type": "laptop",
      "timestamp": "2026-02-18T13:19:29.400034",
      "unit": null
    },
    {
      "name": "system_info.os_version",
      "value": "#1 SMP PREEMPT_DYNAMIC Thu Jun  5 18:30:46 UTC 2025",
      "collector_type": "laptop",
      "timestamp": "2026-02-18T13:19:29.400041",
      "unit": null
    },
    {
      "name": "system_info.os_release",
      "value": "6.6.87.2-microsoft-standard-WSL2",
      "collector_type": "laptop",
      "timestamp": "2026-02-18T13:19:29.400047",
      "unit": null
    }
  ]
}

and then recreate the list of metric objects. (example),

{
  "status": "success",
  "timestamp": "2026-02-18T13:21:13.067130",
  "count": 46,
  "data": [
    "Metric(name='system_info.hostname', value='Junior', collector_type='laptop', timestamp='2026-02-18T13:19:29.399974')",
    "Metric(name='system_info.os', value='Linux', collector_type='laptop', timestamp='2026-02-18T13:19:29.400034')",
    "Metric(name='system_info.os_version', value='#1 SMP PREEMPT_DYNAMIC Thu Jun  5 18:30:46 UTC 2025', collector_type='laptop', timestamp='2026-02-18T13:19:29.400041')",
    "Metric(name='system_info.os_release', value='6.6.87.2-microsoft-standard-WSL2', collector_type='laptop', timestamp='2026-02-18T13:19:29.400047')",
    "Metric(name='system_info.architecture', value='x86_64', collector_type='laptop', timestamp='2026-02-18T13:19:29.400053')",
    "Metric(name='system_info.processor', value='x86_64', collector_type='laptop', timestamp='2026-02-18T13:19:29.400059')",
    "Metric(name='cpu.usage_percent', value=0.7, collector_type='laptop', timestamp='2026-02-18T13:19:29.400068', unit='%')",
    "Metric(name='cpu.count_physical', value=6, collector_type='laptop', timestamp='2026-02-18T13:19:29.400090')",
    "Metric(name='cpu.count_logical', value=12, collector_type='laptop', timestamp='2026-02-18T13:19:29.400096')",
    "Metric(name='cpu.frequency_current_mhz', value=2611.2, collector_type='laptop', timestamp='2026-02-18T13:19:29.400102')",
    "Metric(name='cpu.frequency_min_mhz', value=0.0, collector_type='laptop', timestamp='2026-02-18T13:19:29.400108')",
    "Metric(name='cpu.frequency_max_mhz', value=0.0, collector_type='laptop', timestamp='2026-02-18T13:19:29.400116')",
    "Metric(name='memory.total_gb', value=7.6, collector_type='laptop', timestamp='2026-02-18T13:19:29.400122', unit='GB')",
    "Metric(name='memory.used_gb', value=4.0, collector_type='laptop', timestamp='2026-02-18T13:19:29.400127', unit='GB')",
  ]
}

and insert into our sql database

