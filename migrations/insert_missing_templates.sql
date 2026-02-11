-- Insert missing templates: outside-cleaning and carpet-cleaning
-- This migration adds the two new templates to the form_templates table
-- PostgreSQL version

-- Insert Outside Cleaning template
INSERT INTO form_templates (
    template_id,
    user_id,
    name,
    description,
    image,
    color,
    is_system_template,
    is_active,
    template_data
) VALUES (
    'outside-cleaning',
    NULL,
    'Outside Cleaning',
    'Exterior cleaning services for buildings and outdoor spaces.',
    'https://res.cloudinary.com/dxqum9ywx/image/upload/v1770247865/outside_cleaning_acgpg4.jpg',
    '#1a1a1a',
    true,
    true,
    '{}'::jsonb
) ON CONFLICT (template_id) DO UPDATE SET
    name = 'Outside Cleaning',
    description = 'Exterior cleaning services for buildings and outdoor spaces.',
    image = 'https://res.cloudinary.com/dxqum9ywx/image/upload/v1770247865/outside_cleaning_acgpg4.jpg';

-- Insert Carpet Cleaning template
INSERT INTO form_templates (
    template_id,
    user_id,
    name,
    description,
    image,
    color,
    is_system_template,
    is_active,
    template_data
) VALUES (
    'carpet-cleaning',
    NULL,
    'Carpet Cleaning',
    'Professional carpet and upholstery cleaning services.',
    'https://images.unsplash.com/photo-1527515637462-cff94eecc1ac?ixlib=rb-4.0.3&ixid=M3wxMjA3fDB8MHxwaG90by1wYWdlfHx8fGVufDB8fHx8fA%3D%3D&auto=format&fit=crop&w=1000&q=80',
    '#1a1a1a',
    true,
    true,
    '{}'::jsonb
) ON CONFLICT (template_id) DO UPDATE SET
    name = 'Carpet Cleaning',
    description = 'Professional carpet and upholstery cleaning services.',
    image = 'https://images.unsplash.com/photo-1527515637462-cff94eecc1ac?ixlib=rb-4.0.3&ixid=M3wxMjA3fDB8MHxwaG90by1wYWdlfHx8fGVufDB8fHx8fA%3D%3D&auto=format&fit=crop&w=1000&q=80';
