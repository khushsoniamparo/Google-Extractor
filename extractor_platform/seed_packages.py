import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from jobs.models import Package

def seed():
    # Only seed if empty
    if Package.objects.exists():
        print("Packages already exist. Skipping seed.")
        return

    packages = [
        {
            'name': 'Starter',
            'price': '$49/mo',
            'lead_limit': 2000,
            'grid_strategies': 'search,grid',
            'features': '2,000 Leads / month, 12x12 Grid Strategy, Email Support',
            'is_featured': False
        },
        {
            'name': 'Professional',
            'price': '$99/mo',
            'lead_limit': 10000,
            'grid_strategies': 'search,grid,local',
            'features': '10,000 Leads / month, All Grid Strategies, Bulk Discovery Mode, Priority Support',
            'is_featured': True
        },
        {
            'name': 'Enterprise',
            'price': '$249/mo',
            'lead_limit': 500000, # Large placeholder
            'grid_strategies': 'search,grid,local',
            'features': 'Unlimited Leads, Custom Grid Sizes, API Access, Dedicated Support',
            'is_featured': False
        }
    ]

    for p in packages:
        Package.objects.create(**p)
    print(f"Successfully seeded {len(packages)} tiers.")

if __name__ == '__main__':
    seed()
