-- Migration: Add Scope Templates for Multiple Industries
-- Populates the scope_template column for 7 industry templates with comprehensive service areas and tasks
-- Templates: Medical Facility, Fitness/Gym, Office Building, Retail Store, Warehouse/Industrial, School/Daycare, Restaurant/Cafe

-- ============================================================
-- 1. MEDICAL FACILITY TEMPLATE
-- ============================================================
-- Update the Medical Facility template with the complete scope template
UPDATE form_templates
SET scope_template = '{
  "template_name": "Medical Facility",
  "requires_medical_disclaimer": true,
  "frequency_required": true,
  "serviceAreas": [
    {
      "id": "entrance-lobby-waiting-area",
      "name": "Entrance / Lobby / Waiting Area",
      "icon": "🚶",
      "tasks": [
        {
          "id": "entrance-lobby-waiting-area-task-1",
          "label": "Clean and disinfect entrance glass doors (interior/exterior reachable)"
        },
        {
          "id": "entrance-lobby-waiting-area-task-2",
          "label": "Spot clean walls and doors"
        },
        {
          "id": "entrance-lobby-waiting-area-task-3",
          "label": "Vacuum carpeted areas"
        },
        {
          "id": "entrance-lobby-waiting-area-task-4",
          "label": "Sweep and mop hard floors with hospital-grade disinfectant"
        },
        {
          "id": "entrance-lobby-waiting-area-task-5",
          "label": "Dust and disinfect reception desk"
        },
        {
          "id": "entrance-lobby-waiting-area-task-6",
          "label": "Disinfect waiting room chairs and armrests"
        },
        {
          "id": "entrance-lobby-waiting-area-task-7",
          "label": "Clean and disinfect high-touch surfaces"
        },
        {
          "id": "entrance-lobby-waiting-area-task-8",
          "label": "Empty trash receptacles and replace liners"
        },
        {
          "id": "entrance-lobby-waiting-area-task-9",
          "label": "Dust horizontal surfaces"
        },
        {
          "id": "entrance-lobby-waiting-area-task-10",
          "label": "Clean interior windows and glass partitions"
        },
        {
          "id": "entrance-lobby-waiting-area-task-11",
          "label": "Clean baseboards (spot clean or scheduled detail)"
        },
        {
          "id": "entrance-lobby-waiting-area-task-12",
          "label": "Sanitize check-in kiosks or touchscreens"
        }
      ]
    },
    {
      "id": "exam-treatment-rooms",
      "name": "Exam / Treatment Rooms",
      "icon": "🏥",
      "tasks": [
        {
          "id": "exam-treatment-rooms-task-1",
          "label": "Disinfect exam tables (non-clinical equipment surfaces only)"
        },
        {
          "id": "exam-treatment-rooms-task-2",
          "label": "Disinfect countertops and cabinets (exterior surfaces)"
        },
        {
          "id": "exam-treatment-rooms-task-3",
          "label": "Clean and disinfect sinks and fixtures"
        },
        {
          "id": "exam-treatment-rooms-task-4",
          "label": "Mop floors with EPA-approved disinfectant"
        },
        {
          "id": "exam-treatment-rooms-task-5",
          "label": "Clean and disinfect door handles and push plates"
        },
        {
          "id": "exam-treatment-rooms-task-6",
          "label": "Wipe down chairs and stools"
        },
        {
          "id": "exam-treatment-rooms-task-7",
          "label": "Spot clean walls"
        },
        {
          "id": "exam-treatment-rooms-task-8",
          "label": "Clean interior glass"
        },
        {
          "id": "exam-treatment-rooms-task-9",
          "label": "Empty trash and replace liners"
        },
        {
          "id": "exam-treatment-rooms-task-10",
          "label": "Remove regulated medical waste (if contracted)"
        },
        {
          "id": "exam-treatment-rooms-task-11",
          "label": "Restock soap and paper products (if included in contract)"
        }
      ]
    },
    {
      "id": "nurses-station-admin-stations",
      "name": "Nurses Station / Admin Stations",
      "icon": "💼",
      "tasks": [
        {
          "id": "nurses-station-admin-stations-task-1",
          "label": "Dust and wipe desk surfaces (clear areas only)"
        },
        {
          "id": "nurses-station-admin-stations-task-2",
          "label": "Sanitize phones and keyboards (surface wipe only)"
        },
        {
          "id": "nurses-station-admin-stations-task-3",
          "label": "Disinfect high-touch areas"
        },
        {
          "id": "nurses-station-admin-stations-task-4",
          "label": "Mop floors with disinfectant"
        },
        {
          "id": "nurses-station-admin-stations-task-5",
          "label": "Empty trash"
        },
        {
          "id": "nurses-station-admin-stations-task-6",
          "label": "Clean light switches and cabinet handles"
        }
      ]
    },
    {
      "id": "procedure-rooms-non-surgical",
      "name": "Procedure Rooms (Non-Surgical)",
      "icon": "🧪",
      "tasks": [
        {
          "id": "procedure-rooms-non-surgical-task-1",
          "label": "Disinfect all exposed surfaces"
        },
        {
          "id": "procedure-rooms-non-surgical-task-2",
          "label": "Clean and disinfect sinks"
        },
        {
          "id": "procedure-rooms-non-surgical-task-3",
          "label": "Mop floors with medical-grade disinfectant"
        },
        {
          "id": "procedure-rooms-non-surgical-task-4",
          "label": "Clean stainless steel surfaces"
        },
        {
          "id": "procedure-rooms-non-surgical-task-5",
          "label": "Empty trash and regulated waste (if contracted)"
        },
        {
          "id": "procedure-rooms-non-surgical-task-6",
          "label": "Spot clean walls and doors"
        }
      ]
    },
    {
      "id": "surgical-suite-if-applicable",
      "name": "Surgical Suite (If Applicable)",
      "icon": "⚠️",
      "tasks": [
        {
          "id": "surgical-suite-if-applicable-task-1",
          "label": "Mop floors with approved disinfectant"
        },
        {
          "id": "surgical-suite-if-applicable-task-2",
          "label": "Clean exterior surfaces of equipment"
        },
        {
          "id": "surgical-suite-if-applicable-task-3",
          "label": "Wipe down stainless steel fixtures"
        },
        {
          "id": "surgical-suite-if-applicable-task-4",
          "label": "Disinfect door handles and push plates"
        },
        {
          "id": "surgical-suite-if-applicable-task-5",
          "label": "Remove waste per facility protocol"
        }
      ]
    },
    {
      "id": "laboratory-areas-if-applicable",
      "name": "Laboratory Areas (If Applicable)",
      "icon": "🧪",
      "tasks": [
        {
          "id": "laboratory-areas-if-applicable-task-1",
          "label": "Mop floors with disinfectant"
        },
        {
          "id": "laboratory-areas-if-applicable-task-2",
          "label": "Wipe accessible countertops (non-sensitive areas)"
        },
        {
          "id": "laboratory-areas-if-applicable-task-3",
          "label": "Empty trash"
        },
        {
          "id": "laboratory-areas-if-applicable-task-4",
          "label": "Clean sinks"
        },
        {
          "id": "laboratory-areas-if-applicable-task-5",
          "label": "Disinfect high-touch surfaces"
        }
      ]
    },
    {
      "id": "restrooms-patient-staff",
      "name": "Restrooms (Patient & Staff)",
      "icon": "🚻",
      "tasks": [
        {
          "id": "restrooms-patient-staff-task-1",
          "label": "Clean and disinfect toilets and urinals"
        },
        {
          "id": "restrooms-patient-staff-task-2",
          "label": "Clean and disinfect sinks and counters"
        },
        {
          "id": "restrooms-patient-staff-task-3",
          "label": "Clean mirrors"
        },
        {
          "id": "restrooms-patient-staff-task-4",
          "label": "Disinfect partitions and doors"
        },
        {
          "id": "restrooms-patient-staff-task-5",
          "label": "Mop floors with hospital-grade disinfectant"
        },
        {
          "id": "restrooms-patient-staff-task-6",
          "label": "Restock paper towels, toilet paper, and soap"
        },
        {
          "id": "restrooms-patient-staff-task-7",
          "label": "Empty sanitary receptacles"
        },
        {
          "id": "restrooms-patient-staff-task-8",
          "label": "Disinfect high-touch points"
        }
      ]
    },
    {
      "id": "break-room-staff-kitchen",
      "name": "Break Room / Staff Kitchen",
      "icon": "☕",
      "tasks": [
        {
          "id": "break-room-staff-kitchen-task-1",
          "label": "Clean and sanitize countertops"
        },
        {
          "id": "break-room-staff-kitchen-task-2",
          "label": "Clean sinks"
        },
        {
          "id": "break-room-staff-kitchen-task-3",
          "label": "Wipe exterior of appliances"
        },
        {
          "id": "break-room-staff-kitchen-task-4",
          "label": "Clean microwave interior"
        },
        {
          "id": "break-room-staff-kitchen-task-5",
          "label": "Mop floors"
        },
        {
          "id": "break-room-staff-kitchen-task-6",
          "label": "Empty trash"
        },
        {
          "id": "break-room-staff-kitchen-task-7",
          "label": "Spot clean walls"
        }
      ]
    },
    {
      "id": "offices-administrative-areas",
      "name": "Offices / Administrative Areas",
      "icon": "📊",
      "tasks": [
        {
          "id": "offices-administrative-areas-task-1",
          "label": "Dust desks (clear surfaces only)"
        },
        {
          "id": "offices-administrative-areas-task-2",
          "label": "Vacuum carpeted areas"
        },
        {
          "id": "offices-administrative-areas-task-3",
          "label": "Mop hard floors"
        },
        {
          "id": "offices-administrative-areas-task-4",
          "label": "Clean interior glass"
        },
        {
          "id": "offices-administrative-areas-task-5",
          "label": "Empty trash"
        },
        {
          "id": "offices-administrative-areas-task-6",
          "label": "Disinfect high-touch surfaces"
        }
      ]
    },
    {
      "id": "hallways-corridors",
      "name": "Hallways / Corridors",
      "icon": "🚶",
      "tasks": [
        {
          "id": "hallways-corridors-task-1",
          "label": "Mop floors with disinfectant"
        },
        {
          "id": "hallways-corridors-task-2",
          "label": "Vacuum carpet runners"
        },
        {
          "id": "hallways-corridors-task-3",
          "label": "Clean handrails"
        },
        {
          "id": "hallways-corridors-task-4",
          "label": "Spot clean walls and doors"
        },
        {
          "id": "hallways-corridors-task-5",
          "label": "Disinfect door handles and push plates"
        },
        {
          "id": "hallways-corridors-task-6",
          "label": "Empty trash receptacles"
        }
      ]
    },
    {
      "id": "elevator-if-applicable",
      "name": "Elevator (If Applicable)",
      "icon": "🏢",
      "tasks": [
        {
          "id": "elevator-if-applicable-task-1",
          "label": "Clean and disinfect control panels"
        },
        {
          "id": "elevator-if-applicable-task-2",
          "label": "Wipe down interior walls"
        },
        {
          "id": "elevator-if-applicable-task-3",
          "label": "Mop floors"
        },
        {
          "id": "elevator-if-applicable-task-4",
          "label": "Clean mirrors"
        },
        {
          "id": "elevator-if-applicable-task-5",
          "label": "Disinfect handrails"
        }
      ]
    },
    {
      "id": "facility-wide-high-touch-disinfection-add-on",
      "name": "Facility-Wide High-Touch Disinfection (Add-On)",
      "icon": "🤚",
      "tasks": [
        {
          "id": "facility-wide-high-touch-disinfection-add-on-task-1",
          "label": "Disinfect door handles"
        },
        {
          "id": "facility-wide-high-touch-disinfection-add-on-task-2",
          "label": "Disinfect push plates"
        },
        {
          "id": "facility-wide-high-touch-disinfection-add-on-task-3",
          "label": "Disinfect light switches"
        },
        {
          "id": "facility-wide-high-touch-disinfection-add-on-task-4",
          "label": "Disinfect handrails"
        },
        {
          "id": "facility-wide-high-touch-disinfection-add-on-task-5",
          "label": "Disinfect elevator buttons"
        },
        {
          "id": "facility-wide-high-touch-disinfection-add-on-task-6",
          "label": "Sanitize check-in kiosks"
        },
        {
          "id": "facility-wide-high-touch-disinfection-add-on-task-7",
          "label": "Disinfect waiting room armrests"
        },
        {
          "id": "facility-wide-high-touch-disinfection-add-on-task-8",
          "label": "Sanitize shared pens"
        },
        {
          "id": "facility-wide-high-touch-disinfection-add-on-task-9",
          "label": "Disinfect water fountain buttons"
        }
      ]
    }
  ],
  "compliance_notes": [
    "Cleaning performed using EPA-approved disinfectants.",
    "Services do not include sterilization of medical instruments.",
    "Biohazard waste handling only if explicitly contracted.",
    "Sharps disposal excluded unless specified in contract.",
    "Facility responsible for maintaining regulatory compliance protocols."
  ]
}'::json,
updated_at = NOW()
WHERE template_id = 'medical'
  AND is_system_template = true;

-- Verify the update
SELECT 
  id,
  template_id,
  name,
  json_array_length(scope_template->'serviceAreas') as service_areas_count,
  json_array_length(scope_template->'compliance_notes') as compliance_notes_count
FROM form_templates
WHERE template_id = 'medical'
  AND is_system_template = true;


-- ============================================================
-- 2. FITNESS / GYM TEMPLATE
-- ============================================================
UPDATE form_templates
SET scope_template = '{
  "template_name": "Fitness / Gym",
  "frequency_required": true,
  "serviceAreas": [
    {
      "id": "lobby-front-desk",
      "name": "Lobby / Front Desk",
      "icon": "🏋️",
      "tasks": [
        {"id": "lobby-front-desk-task-1", "label": "Clean and sanitize front desk counters"},
        {"id": "lobby-front-desk-task-2", "label": "Disinfect check-in kiosks and keypads"},
        {"id": "lobby-front-desk-task-3", "label": "Clean interior glass doors (accessible areas)"},
        {"id": "lobby-front-desk-task-4", "label": "Vacuum carpeted areas"},
        {"id": "lobby-front-desk-task-5", "label": "Sweep and mop hard floors"},
        {"id": "lobby-front-desk-task-6", "label": "Empty trash receptacles and replace liners"},
        {"id": "lobby-front-desk-task-7", "label": "Disinfect high-touch surfaces"}
      ]
    },
    {
      "id": "workout-floor",
      "name": "Workout Floor (Cardio & Strength Areas)",
      "icon": "💪",
      "tasks": [
        {"id": "workout-floor-task-1", "label": "Disinfect fitness equipment surfaces (external wipe only)"},
        {"id": "workout-floor-task-2", "label": "Clean and disinfect weight benches"},
        {"id": "workout-floor-task-3", "label": "Clean and sanitize free weights (accessible surfaces)"},
        {"id": "workout-floor-task-4", "label": "Vacuum rubber flooring and mats"},
        {"id": "workout-floor-task-5", "label": "Mop hard surface floors with disinfectant"},
        {"id": "workout-floor-task-6", "label": "Spot clean mirrors"},
        {"id": "workout-floor-task-7", "label": "Empty trash receptacles"}
      ]
    },
    {
      "id": "group-fitness-rooms",
      "name": "Group Fitness Rooms / Studios",
      "icon": "🧘",
      "tasks": [
        {"id": "group-fitness-rooms-task-1", "label": "Vacuum or mop studio floors"},
        {"id": "group-fitness-rooms-task-2", "label": "Disinfect mats and shared equipment (external wipe)"},
        {"id": "group-fitness-rooms-task-3", "label": "Clean mirrors"},
        {"id": "group-fitness-rooms-task-4", "label": "Dust accessible surfaces"},
        {"id": "group-fitness-rooms-task-5", "label": "Disinfect high-touch surfaces"},
        {"id": "group-fitness-rooms-task-6", "label": "Empty trash"}
      ]
    },
    {
      "id": "locker-rooms",
      "name": "Locker Rooms",
      "icon": "🔐",
      "tasks": [
        {"id": "locker-rooms-task-1", "label": "Clean and disinfect lockers (exterior surfaces)"},
        {"id": "locker-rooms-task-2", "label": "Clean and disinfect benches"},
        {"id": "locker-rooms-task-3", "label": "Sweep and mop floors with disinfectant"},
        {"id": "locker-rooms-task-4", "label": "Disinfect high-touch surfaces"},
        {"id": "locker-rooms-task-5", "label": "Empty trash receptacles"},
        {"id": "locker-rooms-task-6", "label": "Spot clean walls"}
      ]
    },
    {
      "id": "showers-wet-areas",
      "name": "Showers / Wet Areas",
      "icon": "🚿",
      "tasks": [
        {"id": "showers-wet-areas-task-1", "label": "Clean and disinfect shower walls and floors"},
        {"id": "showers-wet-areas-task-2", "label": "Remove soap residue and mineral buildup (accessible areas)"},
        {"id": "showers-wet-areas-task-3", "label": "Clean and disinfect sinks and countertops"},
        {"id": "showers-wet-areas-task-4", "label": "Clean mirrors"},
        {"id": "showers-wet-areas-task-5", "label": "Mop and disinfect floors"},
        {"id": "showers-wet-areas-task-6", "label": "Disinfect high-touch surfaces"}
      ]
    },
    {
      "id": "restrooms-gym",
      "name": "Restrooms",
      "icon": "🚻",
      "tasks": [
        {"id": "restrooms-gym-task-1", "label": "Clean and disinfect toilets and urinals"},
        {"id": "restrooms-gym-task-2", "label": "Clean and disinfect sinks and countertops"},
        {"id": "restrooms-gym-task-3", "label": "Clean mirrors"},
        {"id": "restrooms-gym-task-4", "label": "Disinfect partitions and doors"},
        {"id": "restrooms-gym-task-5", "label": "Mop and disinfect floors"},
        {"id": "restrooms-gym-task-6", "label": "Restock paper products and soap (client supplied)"},
        {"id": "restrooms-gym-task-7", "label": "Empty sanitary receptacles"}
      ]
    },
    {
      "id": "sauna-steam-room",
      "name": "Sauna / Steam Room (If Applicable)",
      "icon": "♨️",
      "tasks": [
        {"id": "sauna-steam-room-task-1", "label": "Wipe down benches and seating areas"},
        {"id": "sauna-steam-room-task-2", "label": "Disinfect high-touch surfaces"},
        {"id": "sauna-steam-room-task-3", "label": "Clean floors"},
        {"id": "sauna-steam-room-task-4", "label": "Remove visible debris"}
      ]
    },
    {
      "id": "hallways-common-areas-gym",
      "name": "Hallways / Common Areas",
      "icon": "🚶",
      "tasks": [
        {"id": "hallways-common-areas-gym-task-1", "label": "Vacuum carpeted areas"},
        {"id": "hallways-common-areas-gym-task-2", "label": "Sweep and mop hard floors"},
        {"id": "hallways-common-areas-gym-task-3", "label": "Spot clean walls and doors"},
        {"id": "hallways-common-areas-gym-task-4", "label": "Disinfect door handles and push plates"},
        {"id": "hallways-common-areas-gym-task-5", "label": "Empty trash receptacles"}
      ]
    }
  ],
  "compliance_notes": [
    "Cleaning excludes maintenance or repair of fitness equipment.",
    "Disinfection performed using gym-safe, non-corrosive products.",
    "High-traffic areas may require increased service frequency."
  ]
}'::json,
updated_at = NOW()
WHERE template_id = 'gym'
  AND is_system_template = true;

-- ============================================================
-- 3. OFFICE BUILDING TEMPLATE
-- ============================================================
UPDATE form_templates
SET scope_template = '{
  "template_name": "Office Building",
  "frequency_required": true,
  "serviceAreas": [
    {
      "id": "lobby-reception-area",
      "name": "Lobby / Reception Area",
      "icon": "🏢",
      "tasks": [
        {"id": "lobby-reception-area-task-1", "label": "Dust and wipe reception desk surfaces"},
        {"id": "lobby-reception-area-task-2", "label": "Clean interior glass doors and partitions (accessible areas)"},
        {"id": "lobby-reception-area-task-3", "label": "Vacuum carpeted areas"},
        {"id": "lobby-reception-area-task-4", "label": "Sweep and mop hard floors"},
        {"id": "lobby-reception-area-task-5", "label": "Spot clean walls and baseboards"},
        {"id": "lobby-reception-area-task-6", "label": "Disinfect high-touch surfaces"},
        {"id": "lobby-reception-area-task-7", "label": "Empty trash receptacles and replace liners"}
      ]
    },
    {
      "id": "open-office-areas",
      "name": "Open Office Areas / Workstations",
      "icon": "💼",
      "tasks": [
        {"id": "open-office-areas-task-1", "label": "Dust desks (excluding paperwork and personal items)"},
        {"id": "open-office-areas-task-2", "label": "Dust cubicle partitions (reachable areas)"},
        {"id": "open-office-areas-task-3", "label": "Vacuum carpeted areas"},
        {"id": "open-office-areas-task-4", "label": "Sweep and mop hard surface floors"},
        {"id": "open-office-areas-task-5", "label": "Disinfect high-touch surfaces (door handles, light switches)"},
        {"id": "open-office-areas-task-6", "label": "Empty trash and recycling bins"},
        {"id": "open-office-areas-task-7", "label": "Spot clean glass and interior windows (accessible areas)"}
      ]
    },
    {
      "id": "private-offices",
      "name": "Private Offices",
      "icon": "🚪",
      "tasks": [
        {"id": "private-offices-task-1", "label": "Dust accessible surfaces"},
        {"id": "private-offices-task-2", "label": "Vacuum carpets"},
        {"id": "private-offices-task-3", "label": "Sweep and mop hard floors"},
        {"id": "private-offices-task-4", "label": "Disinfect high-touch points"},
        {"id": "private-offices-task-5", "label": "Empty trash receptacles"},
        {"id": "private-offices-task-6", "label": "Spot clean interior glass"}
      ]
    },
    {
      "id": "conference-meeting-rooms",
      "name": "Conference / Meeting Rooms",
      "icon": "📊",
      "tasks": [
        {"id": "conference-meeting-rooms-task-1", "label": "Clean and sanitize conference tables"},
        {"id": "conference-meeting-rooms-task-2", "label": "Dust chairs and furniture"},
        {"id": "conference-meeting-rooms-task-3", "label": "Vacuum floors"},
        {"id": "conference-meeting-rooms-task-4", "label": "Sweep and mop hard surfaces"},
        {"id": "conference-meeting-rooms-task-5", "label": "Clean whiteboards (dry erase only)"},
        {"id": "conference-meeting-rooms-task-6", "label": "Disinfect high-touch surfaces"},
        {"id": "conference-meeting-rooms-task-7", "label": "Empty trash"}
      ]
    },
    {
      "id": "break-room-kitchenette",
      "name": "Break Room / Kitchenette",
      "icon": "☕",
      "tasks": [
        {"id": "break-room-kitchenette-task-1", "label": "Clean and sanitize countertops"},
        {"id": "break-room-kitchenette-task-2", "label": "Clean sink and polish fixtures"},
        {"id": "break-room-kitchenette-task-3", "label": "Wipe exterior of appliances"},
        {"id": "break-room-kitchenette-task-4", "label": "Clean microwave interior and exterior"},
        {"id": "break-room-kitchenette-task-5", "label": "Sweep and mop floors"},
        {"id": "break-room-kitchenette-task-6", "label": "Empty trash and replace liners"},
        {"id": "break-room-kitchenette-task-7", "label": "Disinfect tables and chairs"}
      ]
    },
    {
      "id": "restrooms-office",
      "name": "Restrooms",
      "icon": "🚻",
      "tasks": [
        {"id": "restrooms-office-task-1", "label": "Clean and disinfect toilets and urinals"},
        {"id": "restrooms-office-task-2", "label": "Clean and disinfect sinks and countertops"},
        {"id": "restrooms-office-task-3", "label": "Clean mirrors"},
        {"id": "restrooms-office-task-4", "label": "Disinfect partitions and doors"},
        {"id": "restrooms-office-task-5", "label": "Mop and disinfect floors"},
        {"id": "restrooms-office-task-6", "label": "Restock paper products and soap (client supplied)"},
        {"id": "restrooms-office-task-7", "label": "Empty sanitary receptacles"},
        {"id": "restrooms-office-task-8", "label": "Disinfect high-touch surfaces"}
      ]
    },
    {
      "id": "hallways-common-areas-office",
      "name": "Hallways / Common Areas",
      "icon": "🚶",
      "tasks": [
        {"id": "hallways-common-areas-office-task-1", "label": "Vacuum carpeted areas"},
        {"id": "hallways-common-areas-office-task-2", "label": "Sweep and mop hard floors"},
        {"id": "hallways-common-areas-office-task-3", "label": "Spot clean walls and doors"},
        {"id": "hallways-common-areas-office-task-4", "label": "Disinfect door handles and push plates"},
        {"id": "hallways-common-areas-office-task-5", "label": "Empty trash receptacles"}
      ]
    },
    {
      "id": "stairwells",
      "name": "Stairwells",
      "icon": "🪜",
      "tasks": [
        {"id": "stairwells-task-1", "label": "Sweep stairs and landings"},
        {"id": "stairwells-task-2", "label": "Spot mop as needed"},
        {"id": "stairwells-task-3", "label": "Dust handrails"},
        {"id": "stairwells-task-4", "label": "Disinfect handrails and high-touch surfaces"},
        {"id": "stairwells-task-5", "label": "Remove cobwebs from corners"}
      ]
    },
    {
      "id": "elevators",
      "name": "Elevators",
      "icon": "🛗",
      "tasks": [
        {"id": "elevators-task-1", "label": "Clean and polish interior panels"},
        {"id": "elevators-task-2", "label": "Clean mirrors"},
        {"id": "elevators-task-3", "label": "Vacuum or mop floors"},
        {"id": "elevators-task-4", "label": "Disinfect buttons and high-touch surfaces"},
        {"id": "elevators-task-5", "label": "Spot clean doors"}
      ]
    }
  ],
  "compliance_notes": [
    "Cleaning excludes handling confidential documents.",
    "IT equipment cleaning limited to exterior surface wipe only.",
    "After-hours service recommended to minimize disruption."
  ]
}'::json,
updated_at = NOW()
WHERE template_id = 'office'
  AND is_system_template = true;

-- ============================================================
-- 4. RETAIL STORE TEMPLATE
-- ============================================================
UPDATE form_templates
SET scope_template = '{
  "template_name": "Retail Store",
  "frequency_required": true,
  "serviceAreas": [
    {
      "id": "entrance-storefront",
      "name": "Entrance / Storefront",
      "icon": "🛍️",
      "tasks": [
        {"id": "entrance-storefront-task-1", "label": "Clean interior and accessible exterior glass doors"},
        {"id": "entrance-storefront-task-2", "label": "Spot clean storefront windows (reachable areas)"},
        {"id": "entrance-storefront-task-3", "label": "Clean door handles and push plates"},
        {"id": "entrance-storefront-task-4", "label": "Sweep entrance area"},
        {"id": "entrance-storefront-task-5", "label": "Mop hard surface floors"},
        {"id": "entrance-storefront-task-6", "label": "Remove cobwebs from entry corners"}
      ]
    },
    {
      "id": "sales-floor",
      "name": "Sales Floor",
      "icon": "🛒",
      "tasks": [
        {"id": "sales-floor-task-1", "label": "Dust shelves and display units (accessible areas)"},
        {"id": "sales-floor-task-2", "label": "Dust merchandise displays (non-fragile items only)"},
        {"id": "sales-floor-task-3", "label": "Sweep and mop hard floors"},
        {"id": "sales-floor-task-4", "label": "Vacuum carpeted areas"},
        {"id": "sales-floor-task-5", "label": "Spot clean glass and mirrors"},
        {"id": "sales-floor-task-6", "label": "Disinfect high-touch surfaces"},
        {"id": "sales-floor-task-7", "label": "Empty trash receptacles and replace liners"},
        {"id": "sales-floor-task-8", "label": "Spot clean walls and columns"},
        {"id": "sales-floor-task-9", "label": "Clean baseboards (spot clean or scheduled detail)"}
      ]
    },
    {
      "id": "checkout-pos-area",
      "name": "Checkout / POS Area",
      "icon": "💳",
      "tasks": [
        {"id": "checkout-pos-area-task-1", "label": "Sanitize checkout counters"},
        {"id": "checkout-pos-area-task-2", "label": "Clean conveyor belts (if applicable)"},
        {"id": "checkout-pos-area-task-3", "label": "Disinfect card terminals and POS surfaces (external wipe only)"},
        {"id": "checkout-pos-area-task-4", "label": "Dust display racks and impulse shelves"},
        {"id": "checkout-pos-area-task-5", "label": "Empty trash"},
        {"id": "checkout-pos-area-task-6", "label": "Clean surrounding floors"}
      ]
    },
    {
      "id": "fitting-rooms",
      "name": "Fitting Rooms (If Applicable)",
      "icon": "👔",
      "tasks": [
        {"id": "fitting-rooms-task-1", "label": "Vacuum floors"},
        {"id": "fitting-rooms-task-2", "label": "Clean and polish mirrors"},
        {"id": "fitting-rooms-task-3", "label": "Disinfect benches and seating"},
        {"id": "fitting-rooms-task-4", "label": "Clean hooks and door handles"},
        {"id": "fitting-rooms-task-5", "label": "Remove debris and unwanted items"},
        {"id": "fitting-rooms-task-6", "label": "Spot clean walls"}
      ]
    },
    {
      "id": "stockroom-storage-area",
      "name": "Stockroom / Storage Area",
      "icon": "📦",
      "tasks": [
        {"id": "stockroom-storage-area-task-1", "label": "Sweep floors"},
        {"id": "stockroom-storage-area-task-2", "label": "Remove debris and packaging materials"},
        {"id": "stockroom-storage-area-task-3", "label": "Break down cardboard (if included in contract)"},
        {"id": "stockroom-storage-area-task-4", "label": "Spot mop spills"},
        {"id": "stockroom-storage-area-task-5", "label": "Clean light switches and door handles"}
      ]
    },
    {
      "id": "employee-break-room",
      "name": "Employee Break Room",
      "icon": "☕",
      "tasks": [
        {"id": "employee-break-room-task-1", "label": "Clean and sanitize countertops"},
        {"id": "employee-break-room-task-2", "label": "Clean sink and fixtures"},
        {"id": "employee-break-room-task-3", "label": "Wipe exterior of appliances"},
        {"id": "employee-break-room-task-4", "label": "Clean microwave interior"},
        {"id": "employee-break-room-task-5", "label": "Mop floors"},
        {"id": "employee-break-room-task-6", "label": "Empty trash"},
        {"id": "employee-break-room-task-7", "label": "Spot clean walls"}
      ]
    },
    {
      "id": "restrooms-retail",
      "name": "Restrooms (Customer & Staff)",
      "icon": "🚻",
      "tasks": [
        {"id": "restrooms-retail-task-1", "label": "Clean and disinfect toilets and urinals"},
        {"id": "restrooms-retail-task-2", "label": "Clean and disinfect sinks and countertops"},
        {"id": "restrooms-retail-task-3", "label": "Clean mirrors"},
        {"id": "restrooms-retail-task-4", "label": "Disinfect partitions and doors"},
        {"id": "restrooms-retail-task-5", "label": "Mop and disinfect floors"},
        {"id": "restrooms-retail-task-6", "label": "Restock toilet paper, paper towels, and soap"},
        {"id": "restrooms-retail-task-7", "label": "Empty sanitary receptacles"},
        {"id": "restrooms-retail-task-8", "label": "Disinfect high-touch surfaces"}
      ]
    },
    {
      "id": "hallways-back-areas",
      "name": "Hallways / Back Areas",
      "icon": "🚶",
      "tasks": [
        {"id": "hallways-back-areas-task-1", "label": "Sweep and mop floors"},
        {"id": "hallways-back-areas-task-2", "label": "Vacuum carpeted areas"},
        {"id": "hallways-back-areas-task-3", "label": "Spot clean walls and doors"},
        {"id": "hallways-back-areas-task-4", "label": "Disinfect door handles and push plates"},
        {"id": "hallways-back-areas-task-5", "label": "Empty trash receptacles"}
      ]
    }
  ],
  "compliance_notes": [
    "Cleaning excludes handling of cash or merchandise inventory.",
    "High-value merchandise dusting limited to accessible surfaces only.",
    "After-hours service recommended to avoid customer disruption."
  ]
}'::json,
updated_at = NOW()
WHERE template_id = 'retail'
  AND is_system_template = true;

-- ============================================================
-- 5. WAREHOUSE / INDUSTRIAL FACILITY TEMPLATE
-- ============================================================
UPDATE form_templates
SET scope_template = '{
  "template_name": "Warehouse / Industrial Facility",
  "frequency_required": true,
  "requires_safety_compliance_notice": true,
  "serviceAreas": [
    {
      "id": "loading-docks",
      "name": "Loading Docks",
      "icon": "🚚",
      "tasks": [
        {"id": "loading-docks-task-1", "label": "Sweep dock areas and remove debris"},
        {"id": "loading-docks-task-2", "label": "Spot clean spills (non-hazardous)"},
        {"id": "loading-docks-task-3", "label": "Remove trash and replace liners"},
        {"id": "loading-docks-task-4", "label": "Clean dock doors (interior accessible areas)"},
        {"id": "loading-docks-task-5", "label": "Dust accessible surfaces"}
      ]
    },
    {
      "id": "warehouse-floor",
      "name": "Warehouse Floor",
      "icon": "🏭",
      "tasks": [
        {"id": "warehouse-floor-task-1", "label": "Sweep large floor areas with industrial equipment"},
        {"id": "warehouse-floor-task-2", "label": "Auto-scrub floors (if contracted)"},
        {"id": "warehouse-floor-task-3", "label": "Spot degrease high-traffic areas"},
        {"id": "warehouse-floor-task-4", "label": "Remove debris from corners and edges"},
        {"id": "warehouse-floor-task-5", "label": "Disinfect high-touch surfaces (accessible areas)"}
      ]
    },
    {
      "id": "production-assembly-areas",
      "name": "Production / Assembly Areas (Non-Specialized Equipment)",
      "icon": "⚙️",
      "tasks": [
        {"id": "production-assembly-areas-task-1", "label": "Sweep and mop floors"},
        {"id": "production-assembly-areas-task-2", "label": "Wipe exterior surfaces of machinery (non-sensitive areas only)"},
        {"id": "production-assembly-areas-task-3", "label": "Disinfect high-touch points"},
        {"id": "production-assembly-areas-task-4", "label": "Empty trash receptacles"},
        {"id": "production-assembly-areas-task-5", "label": "Spot clean walls and partitions"}
      ]
    },
    {
      "id": "storage-racking-areas",
      "name": "Storage / Racking Areas",
      "icon": "📦",
      "tasks": [
        {"id": "storage-racking-areas-task-1", "label": "Sweep aisles between racks"},
        {"id": "storage-racking-areas-task-2", "label": "Remove cobwebs from accessible heights"},
        {"id": "storage-racking-areas-task-3", "label": "Dust lower-level racking (reachable areas only)"},
        {"id": "storage-racking-areas-task-4", "label": "Spot clean spills (non-hazardous)"}
      ]
    },
    {
      "id": "offices-administrative-areas-warehouse",
      "name": "Offices / Administrative Areas",
      "icon": "💼",
      "tasks": [
        {"id": "offices-administrative-areas-warehouse-task-1", "label": "Dust accessible surfaces"},
        {"id": "offices-administrative-areas-warehouse-task-2", "label": "Vacuum carpeted areas"},
        {"id": "offices-administrative-areas-warehouse-task-3", "label": "Sweep and mop hard floors"},
        {"id": "offices-administrative-areas-warehouse-task-4", "label": "Disinfect high-touch surfaces"},
        {"id": "offices-administrative-areas-warehouse-task-5", "label": "Empty trash receptacles"},
        {"id": "offices-administrative-areas-warehouse-task-6", "label": "Clean interior glass (accessible areas)"}
      ]
    },
    {
      "id": "break-room-staff-area-warehouse",
      "name": "Break Room / Staff Area",
      "icon": "☕",
      "tasks": [
        {"id": "break-room-staff-area-warehouse-task-1", "label": "Clean and sanitize countertops"},
        {"id": "break-room-staff-area-warehouse-task-2", "label": "Clean sink and polish fixtures"},
        {"id": "break-room-staff-area-warehouse-task-3", "label": "Wipe exterior of appliances"},
        {"id": "break-room-staff-area-warehouse-task-4", "label": "Sweep and mop floors"},
        {"id": "break-room-staff-area-warehouse-task-5", "label": "Empty trash and replace liners"},
        {"id": "break-room-staff-area-warehouse-task-6", "label": "Disinfect tables and chairs"}
      ]
    },
    {
      "id": "restrooms-staff-warehouse",
      "name": "Restrooms (Staff)",
      "icon": "🚻",
      "tasks": [
        {"id": "restrooms-staff-warehouse-task-1", "label": "Clean and disinfect toilets and urinals"},
        {"id": "restrooms-staff-warehouse-task-2", "label": "Clean and disinfect sinks and countertops"},
        {"id": "restrooms-staff-warehouse-task-3", "label": "Clean mirrors"},
        {"id": "restrooms-staff-warehouse-task-4", "label": "Disinfect partitions and stall doors"},
        {"id": "restrooms-staff-warehouse-task-5", "label": "Mop and disinfect floors"},
        {"id": "restrooms-staff-warehouse-task-6", "label": "Restock paper products and soap (client supplied)"},
        {"id": "restrooms-staff-warehouse-task-7", "label": "Empty sanitary receptacles"},
        {"id": "restrooms-staff-warehouse-task-8", "label": "Disinfect high-touch surfaces"}
      ]
    },
    {
      "id": "hallways-common-areas-warehouse",
      "name": "Hallways / Common Areas",
      "icon": "🚶",
      "tasks": [
        {"id": "hallways-common-areas-warehouse-task-1", "label": "Sweep and mop floors"},
        {"id": "hallways-common-areas-warehouse-task-2", "label": "Spot clean walls and doors"},
        {"id": "hallways-common-areas-warehouse-task-3", "label": "Disinfect door handles and push plates"},
        {"id": "hallways-common-areas-warehouse-task-4", "label": "Empty trash receptacles"}
      ]
    },
    {
      "id": "facility-wide-high-touch-disinfection-warehouse",
      "name": "Facility-Wide High-Touch Disinfection",
      "icon": "🤚",
      "tasks": [
        {"id": "facility-wide-high-touch-disinfection-warehouse-task-1", "label": "Disinfect door handles"},
        {"id": "facility-wide-high-touch-disinfection-warehouse-task-2", "label": "Disinfect push plates"},
        {"id": "facility-wide-high-touch-disinfection-warehouse-task-3", "label": "Disinfect light switches"},
        {"id": "facility-wide-high-touch-disinfection-warehouse-task-4", "label": "Disinfect handrails"},
        {"id": "facility-wide-high-touch-disinfection-warehouse-task-5", "label": "Sanitize shared touchpoints"}
      ]
    }
  ],
  "compliance_notes": [
    "Cleaning excludes handling of hazardous materials unless explicitly contracted.",
    "Lockout/tagout procedures remain responsibility of facility staff.",
    "High-elevation cleaning above reachable height excluded unless specified.",
    "Specialized equipment internal cleaning excluded unless contracted.",
    "Facility responsible for OSHA and local safety compliance."
  ]
}'::json,
updated_at = NOW()
WHERE template_id = 'warehouse'
  AND is_system_template = true;

-- ============================================================
-- 6. SCHOOL / DAYCARE FACILITY TEMPLATE
-- ============================================================
UPDATE form_templates
SET scope_template = '{
  "template_name": "School / Daycare Facility",
  "frequency_required": true,
  "requires_child_safety_notice": true,
  "serviceAreas": [
    {
      "id": "main-entrance-lobby-school",
      "name": "Main Entrance / Lobby",
      "icon": "🏫",
      "tasks": [
        {"id": "main-entrance-lobby-school-task-1", "label": "Clean and disinfect entrance doors and glass (accessible areas)"},
        {"id": "main-entrance-lobby-school-task-2", "label": "Vacuum carpeted areas"},
        {"id": "main-entrance-lobby-school-task-3", "label": "Sweep and mop hard floors"},
        {"id": "main-entrance-lobby-school-task-4", "label": "Dust reception desk and furniture"},
        {"id": "main-entrance-lobby-school-task-5", "label": "Disinfect high-touch surfaces"},
        {"id": "main-entrance-lobby-school-task-6", "label": "Empty trash receptacles and replace liners"},
        {"id": "main-entrance-lobby-school-task-7", "label": "Spot clean walls and baseboards"}
      ]
    },
    {
      "id": "classrooms",
      "name": "Classrooms",
      "icon": "📚",
      "tasks": [
        {"id": "classrooms-task-1", "label": "Dust accessible surfaces (excluding teaching materials)"},
        {"id": "classrooms-task-2", "label": "Disinfect desks and tables"},
        {"id": "classrooms-task-3", "label": "Disinfect chairs"},
        {"id": "classrooms-task-4", "label": "Clean whiteboards (dry erase only)"},
        {"id": "classrooms-task-5", "label": "Vacuum carpeted areas or rugs"},
        {"id": "classrooms-task-6", "label": "Sweep and mop hard floors with child-safe disinfectant"},
        {"id": "classrooms-task-7", "label": "Disinfect high-touch surfaces (door handles, light switches)"},
        {"id": "classrooms-task-8", "label": "Empty trash receptacles"},
        {"id": "classrooms-task-9", "label": "Spot clean interior glass"}
      ]
    },
    {
      "id": "infant-toddler-rooms",
      "name": "Infant / Toddler Rooms (If Applicable)",
      "icon": "👶",
      "tasks": [
        {"id": "infant-toddler-rooms-task-1", "label": "Disinfect cribs (exterior surfaces only)"},
        {"id": "infant-toddler-rooms-task-2", "label": "Disinfect changing stations"},
        {"id": "infant-toddler-rooms-task-3", "label": "Clean and disinfect play mats"},
        {"id": "infant-toddler-rooms-task-4", "label": "Sanitize reachable toy storage surfaces"},
        {"id": "infant-toddler-rooms-task-5", "label": "Sweep and mop floors with child-safe disinfectant"},
        {"id": "infant-toddler-rooms-task-6", "label": "Disinfect high-touch surfaces"},
        {"id": "infant-toddler-rooms-task-7", "label": "Empty trash and diaper disposal bins (if contracted)"}
      ]
    },
    {
      "id": "restrooms-student-staff",
      "name": "Restrooms (Student & Staff)",
      "icon": "🚻",
      "tasks": [
        {"id": "restrooms-student-staff-task-1", "label": "Clean and disinfect toilets and urinals"},
        {"id": "restrooms-student-staff-task-2", "label": "Clean and disinfect sinks and counters"},
        {"id": "restrooms-student-staff-task-3", "label": "Clean mirrors"},
        {"id": "restrooms-student-staff-task-4", "label": "Disinfect partitions and stall doors"},
        {"id": "restrooms-student-staff-task-5", "label": "Mop and disinfect floors"},
        {"id": "restrooms-student-staff-task-6", "label": "Restock soap and paper products (client supplied)"},
        {"id": "restrooms-student-staff-task-7", "label": "Empty sanitary receptacles"},
        {"id": "restrooms-student-staff-task-8", "label": "Disinfect high-touch surfaces"}
      ]
    },
    {
      "id": "hallways-corridors-school",
      "name": "Hallways / Corridors",
      "icon": "🚶",
      "tasks": [
        {"id": "hallways-corridors-school-task-1", "label": "Vacuum carpet runners"},
        {"id": "hallways-corridors-school-task-2", "label": "Sweep and mop hard floors"},
        {"id": "hallways-corridors-school-task-3", "label": "Disinfect handrails"},
        {"id": "hallways-corridors-school-task-4", "label": "Spot clean walls and doors"},
        {"id": "hallways-corridors-school-task-5", "label": "Disinfect door handles and push plates"},
        {"id": "hallways-corridors-school-task-6", "label": "Empty trash receptacles"}
      ]
    },
    {
      "id": "cafeteria-lunch-area",
      "name": "Cafeteria / Lunch Area",
      "icon": "🍽️",
      "tasks": [
        {"id": "cafeteria-lunch-area-task-1", "label": "Clean and sanitize tables and seating areas"},
        {"id": "cafeteria-lunch-area-task-2", "label": "Sweep and mop floors"},
        {"id": "cafeteria-lunch-area-task-3", "label": "Disinfect high-touch surfaces"},
        {"id": "cafeteria-lunch-area-task-4", "label": "Spot clean walls"},
        {"id": "cafeteria-lunch-area-task-5", "label": "Empty trash receptacles and replace liners"}
      ]
    },
    {
      "id": "administrative-offices-school",
      "name": "Administrative Offices",
      "icon": "💼",
      "tasks": [
        {"id": "administrative-offices-school-task-1", "label": "Dust accessible surfaces"},
        {"id": "administrative-offices-school-task-2", "label": "Vacuum carpets"},
        {"id": "administrative-offices-school-task-3", "label": "Sweep and mop hard floors"},
        {"id": "administrative-offices-school-task-4", "label": "Disinfect high-touch surfaces"},
        {"id": "administrative-offices-school-task-5", "label": "Empty trash receptacles"},
        {"id": "administrative-offices-school-task-6", "label": "Clean interior glass (accessible areas)"}
      ]
    },
    {
      "id": "gymnasium-activity-room",
      "name": "Gymnasium / Activity Room (If Applicable)",
      "icon": "🏀",
      "tasks": [
        {"id": "gymnasium-activity-room-task-1", "label": "Sweep and mop floors"},
        {"id": "gymnasium-activity-room-task-2", "label": "Disinfect high-touch equipment (non-specialized equipment only)"},
        {"id": "gymnasium-activity-room-task-3", "label": "Spot clean walls"},
        {"id": "gymnasium-activity-room-task-4", "label": "Empty trash receptacles"}
      ]
    },
    {
      "id": "playground-area",
      "name": "Playground Area (Exterior - If Contracted)",
      "icon": "🎪",
      "tasks": [
        {"id": "playground-area-task-1", "label": "Empty trash receptacles"},
        {"id": "playground-area-task-2", "label": "Inspect and spot clean accessible surfaces"},
        {"id": "playground-area-task-3", "label": "Sweep entry walkways"}
      ]
    },
    {
      "id": "facility-wide-high-touch-disinfection-school",
      "name": "Facility-Wide High-Touch Disinfection",
      "icon": "🤚",
      "tasks": [
        {"id": "facility-wide-high-touch-disinfection-school-task-1", "label": "Disinfect door handles"},
        {"id": "facility-wide-high-touch-disinfection-school-task-2", "label": "Disinfect push plates"},
        {"id": "facility-wide-high-touch-disinfection-school-task-3", "label": "Disinfect light switches"},
        {"id": "facility-wide-high-touch-disinfection-school-task-4", "label": "Disinfect handrails"},
        {"id": "facility-wide-high-touch-disinfection-school-task-5", "label": "Disinfect shared surfaces"},
        {"id": "facility-wide-high-touch-disinfection-school-task-6", "label": "Sanitize commonly used touchpoints"}
      ]
    }
  ],
  "compliance_notes": [
    "Cleaning products used must be child-safe and compliant with local regulations.",
    "Services exclude sanitization of personal student belongings.",
    "Toy disinfection limited to exterior wipe unless otherwise specified.",
    "Deep sanitization or biohazard cleanup excluded unless explicitly contracted.",
    "Facility responsible for compliance with state childcare regulations."
  ]
}'::json,
updated_at = NOW()
WHERE template_id = 'school'
  AND is_system_template = true;

-- ============================================================
-- 7. RESTAURANT / CAFE TEMPLATE
-- ============================================================
UPDATE form_templates
SET scope_template = '{
  "template_name": "Restaurant / Cafe",
  "frequency_required": true,
  "requires_food_safety_notice": true,
  "serviceAreas": [
    {
      "id": "dining-area",
      "name": "Dining Area",
      "icon": "🍽️",
      "tasks": [
        {"id": "dining-area-task-1", "label": "Clean and sanitize dining tables and chairs"},
        {"id": "dining-area-task-2", "label": "Disinfect high-touch surfaces"},
        {"id": "dining-area-task-3", "label": "Vacuum carpeted areas (if applicable)"},
        {"id": "dining-area-task-4", "label": "Sweep and mop hard floors with food-safe disinfectant"},
        {"id": "dining-area-task-5", "label": "Spot clean walls and partitions"},
        {"id": "dining-area-task-6", "label": "Clean interior glass and mirrors (accessible areas)"},
        {"id": "dining-area-task-7", "label": "Empty trash receptacles and replace liners"}
      ]
    },
    {
      "id": "bar-area",
      "name": "Bar Area (If Applicable)",
      "icon": "🍸",
      "tasks": [
        {"id": "bar-area-task-1", "label": "Clean and sanitize bar countertops"},
        {"id": "bar-area-task-2", "label": "Wipe exterior surfaces of bar equipment"},
        {"id": "bar-area-task-3", "label": "Disinfect high-touch surfaces"},
        {"id": "bar-area-task-4", "label": "Sweep and mop floors"},
        {"id": "bar-area-task-5", "label": "Empty trash receptacles"}
      ]
    },
    {
      "id": "kitchen-non-food-prep",
      "name": "Kitchen (Non-Food Prep Surfaces Only)",
      "icon": "🍳",
      "tasks": [
        {"id": "kitchen-non-food-prep-task-1", "label": "Sweep and degrease mop floors"},
        {"id": "kitchen-non-food-prep-task-2", "label": "Wipe exterior surfaces of equipment"},
        {"id": "kitchen-non-food-prep-task-3", "label": "Clean and sanitize sinks (non-food contact surfaces)"},
        {"id": "kitchen-non-food-prep-task-4", "label": "Empty trash and replace liners"},
        {"id": "kitchen-non-food-prep-task-5", "label": "Disinfect high-touch points (door handles, switches)"}
      ]
    },
    {
      "id": "food-prep-areas",
      "name": "Food Prep Areas (Limited Scope)",
      "icon": "🔪",
      "tasks": [
        {"id": "food-prep-areas-task-1", "label": "Clean and sanitize non-active prep surfaces"},
        {"id": "food-prep-areas-task-2", "label": "Wipe stainless steel exterior surfaces"},
        {"id": "food-prep-areas-task-3", "label": "Sweep and mop floors with food-safe disinfectant"},
        {"id": "food-prep-areas-task-4", "label": "Spot clean walls and splash zones"}
      ]
    },
    {
      "id": "restrooms-customer-staff-restaurant",
      "name": "Restrooms (Customer & Staff)",
      "icon": "🚻",
      "tasks": [
        {"id": "restrooms-customer-staff-restaurant-task-1", "label": "Clean and disinfect toilets and urinals"},
        {"id": "restrooms-customer-staff-restaurant-task-2", "label": "Clean and disinfect sinks and countertops"},
        {"id": "restrooms-customer-staff-restaurant-task-3", "label": "Clean mirrors"},
        {"id": "restrooms-customer-staff-restaurant-task-4", "label": "Disinfect partitions and stall doors"},
        {"id": "restrooms-customer-staff-restaurant-task-5", "label": "Mop and disinfect floors"},
        {"id": "restrooms-customer-staff-restaurant-task-6", "label": "Restock paper products and soap (client supplied)"},
        {"id": "restrooms-customer-staff-restaurant-task-7", "label": "Empty sanitary receptacles"},
        {"id": "restrooms-customer-staff-restaurant-task-8", "label": "Disinfect high-touch surfaces"}
      ]
    },
    {
      "id": "entryway-host-stand",
      "name": "Entryway / Host Stand",
      "icon": "🚪",
      "tasks": [
        {"id": "entryway-host-stand-task-1", "label": "Clean entrance doors and glass (accessible areas)"},
        {"id": "entryway-host-stand-task-2", "label": "Sweep and mop entry floors"},
        {"id": "entryway-host-stand-task-3", "label": "Disinfect host stand surfaces"},
        {"id": "entryway-host-stand-task-4", "label": "Empty trash receptacles"}
      ]
    },
    {
      "id": "storage-areas-restaurant",
      "name": "Storage Areas",
      "icon": "📦",
      "tasks": [
        {"id": "storage-areas-restaurant-task-1", "label": "Sweep floors"},
        {"id": "storage-areas-restaurant-task-2", "label": "Spot mop as needed"},
        {"id": "storage-areas-restaurant-task-3", "label": "Dust accessible shelving (non-food items only)"},
        {"id": "storage-areas-restaurant-task-4", "label": "Remove cobwebs from corners"}
      ]
    },
    {
      "id": "facility-wide-high-touch-disinfection-restaurant",
      "name": "Facility-Wide High-Touch Disinfection",
      "icon": "🤚",
      "tasks": [
        {"id": "facility-wide-high-touch-disinfection-restaurant-task-1", "label": "Disinfect door handles"},
        {"id": "facility-wide-high-touch-disinfection-restaurant-task-2", "label": "Disinfect push plates"},
        {"id": "facility-wide-high-touch-disinfection-restaurant-task-3", "label": "Disinfect light switches"},
        {"id": "facility-wide-high-touch-disinfection-restaurant-task-4", "label": "Disinfect handrails"},
        {"id": "facility-wide-high-touch-disinfection-restaurant-task-5", "label": "Sanitize shared touchpoints"}
      ]
    }
  ],
  "compliance_notes": [
    "Cleaning performed using food-safe and health-code-compliant products.",
    "Services exclude cleaning of active cooking equipment interiors unless explicitly contracted.",
    "Deep hood, duct, and grease trap cleaning excluded unless specified in contract.",
    "Staff responsible for removal of food products prior to service unless otherwise agreed.",
    "Facility responsible for maintaining local health department compliance."
  ]
}'::json,
updated_at = NOW()
WHERE template_id = 'restaurant'
  AND is_system_template = true;

-- ============================================================
-- VERIFICATION QUERY
-- ============================================================
-- Verify all updates
SELECT 
  id,
  template_id,
  name,
  CASE 
    WHEN scope_template IS NOT NULL THEN json_array_length(scope_template->'serviceAreas')
    ELSE 0
  END as service_areas_count,
  CASE 
    WHEN scope_template IS NOT NULL THEN json_array_length(scope_template->'compliance_notes')
    ELSE 0
  END as compliance_notes_count
FROM form_templates
WHERE template_id IN ('medical', 'gym', 'office', 'retail', 'warehouse', 'school', 'restaurant')
  AND is_system_template = true
ORDER BY template_id;


-- ============================================================
-- CLEANUP: REMOVE RESIDENTIAL TEMPLATES
-- ============================================================
-- Remove residential templates that are no longer supported
-- This includes any templates with 'residential' or 'home' in the template_id

-- Soft delete residential templates (set is_active = false)
UPDATE form_templates
SET is_active = false,
    updated_at = NOW()
WHERE (
  template_id ILIKE '%residential%' 
  OR template_id ILIKE '%home%'
  OR template_id IN ('house', 'apartment', 'condo', 'townhouse')
)
AND is_system_template = true;

-- Show what was deactivated
SELECT 
  id,
  template_id,
  name,
  'DEACTIVATED' as status
FROM form_templates
WHERE (
  template_id ILIKE '%residential%' 
  OR template_id ILIKE '%home%'
  OR template_id IN ('house', 'apartment', 'condo', 'townhouse')
)
AND is_system_template = true;
