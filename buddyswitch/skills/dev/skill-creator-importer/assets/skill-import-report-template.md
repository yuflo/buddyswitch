{
  "execution_summary": "Imported a Codex-native skill package into BuddySwitch.",
  "working_notes": [
    "Include importer decisions and validation caveats."
  ],
  "artifacts": [
    {
      "kind": "skill-import-report",
      "title": "Skill Import Report",
      "summary": "Selection-ready report of imported skill packaging and verification.",
      "content": {
        "task_summary": "Imported and registered one external Codex-native skill package.",
        "changed_files": [
          "buddyswitch/skills/<buddy>/<skill-id>/SKILL.md",
          "buddyswitch/manifest.toml"
        ],
        "implementation_notes": [
          "Generated package preserves the external workflow and BuddySwitch commit guidance.",
          "Manifest registration maps the imported skill to the selected buddy."
        ],
        "verification": {
          "checks_run": [],
          "passed": [],
          "failed": [],
          "blocked": []
        },
        "risks": [],
        "follow_ups": []
      }
    }
  ]
}
