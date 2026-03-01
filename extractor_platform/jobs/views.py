# jobs/views.py
import csv
from django.http import HttpResponse
from django.contrib.auth.models import User
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework_simplejwt.tokens import RefreshToken
from .models import BulkJob, KeywordJob, Place
from .tasks import start_bulk_job


class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        username = request.data.get('username', '').strip()
        password = request.data.get('password', '')
        email = request.data.get('email', '').strip()

        if not username or not password:
            return Response(
                {'error': 'Username and password required'},
                status=400
            )
        if User.objects.filter(username=username).exists():
            return Response(
                {'error': 'Username taken'},
                status=400
            )

        user = User.objects.create_user(
            username=username,
            email=email,
            password=password
        )
        refresh = RefreshToken.for_user(user)
        return Response({
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'username': user.username,
        }, status=201)


class StartBulkJobView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        """
        Input:
        {
            "location": "Jaipur",
            "grid_size": 8,
            "keywords": ["IT Company", "Tech", "Software", "Web Development"]
        }
        """
        location = request.data.get('location', '').strip()
        keywords = request.data.get('keywords', [])
        grid_size = int(request.data.get('grid_size', 8))

        # Validation
        if not location:
            return Response(
                {'error': 'location is required'},
                status=400
            )
        if not keywords or not isinstance(keywords, list):
            return Response(
                {'error': 'keywords must be a non-empty list'},
                status=400
            )
        if len(keywords) > 20:
            return Response(
                {'error': 'Max 20 keywords per job'},
                status=400
            )

        # Clean keywords
        keywords = [k.strip() for k in keywords if k.strip()]
        grid_size = max(3, min(grid_size, 15))

        # Create bulk job
        bulk_job = BulkJob.objects.create(
            user=request.user,
            location=location,
            grid_size=grid_size,
        )

        # Create one KeywordJob per keyword
        for keyword in keywords:
            KeywordJob.objects.create(
                bulk_job=bulk_job,
                keyword=keyword,
            )

        # Fire all keyword jobs in parallel background threads
        import threading
        threading.Thread(
            target=start_bulk_job,
            args=(bulk_job.id,),
            daemon=True
        ).start()

        return Response({
            'bulk_job_id': bulk_job.id,
            'location': location,
            'keywords': keywords,
            'grid_size': grid_size,
            'max_possible_per_keyword': grid_size * grid_size * 120,
            'status': 'running',
        }, status=201)


class EstimateJobView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        location = request.data.get('location', '').strip()
        keywords = request.data.get('keywords', [])
        grid_size = int(request.data.get('grid_size', 8))

        if not location:
            return Response({'error': 'location required'}, status=400)
            
        if not keywords:
            keywords = []
        elif isinstance(keywords, str):
            keywords = [k.strip() for k in keywords.split(',') if k.strip()]

        num_keywords = len(keywords) if keywords else 1
        cells_per_grid = grid_size * grid_size
        zooms_per_cell = 4  # hardcoded derived from ZOOM_LEVELS
        tasks_per_keyword = cells_per_grid * zooms_per_cell
        total_tasks = tasks_per_keyword * num_keywords

        # Computation based on assumptions
        http_concurrency = 30
        playwright_concurrency = 5

        total_time_sec = 10  # base start time for cookies/bounds
        
        for _ in range(num_keywords):
            # http 
            http_batches = max(1, tasks_per_keyword / http_concurrency)
            kw_time = http_batches * 3.5  # ~3.5s per batch
            
            # playwrigtt fallback approx (say 15% get blocked)
            pw_tasks = tasks_per_keyword * 0.15
            pw_batches = max(1, pw_tasks / playwright_concurrency)
            kw_time += pw_batches * 6.0
            
            total_time_sec += kw_time

        return Response({
            'total_cells': cells_per_grid * num_keywords,
            'total_requests': total_tasks,
            'estimated_seconds': int(total_time_sec)
        })

class BulkJobStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, bulk_job_id):
        try:
            bulk_job = BulkJob.objects.prefetch_related(
                'keyword_jobs'
            ).get(id=bulk_job_id, user=request.user)
        except BulkJob.DoesNotExist:
            return Response({'error': 'Not found'}, status=404)

        keyword_statuses = []
        for kj in bulk_job.keyword_jobs.all():
            keyword_statuses.append({
                'keyword_job_id': kj.id,
                'keyword': kj.keyword,
                'status': kj.status,
                'status_message': kj.status_message,
                'progress_percent': kj.progress_percent,
                'cells_done': kj.cells_done,
                'total_cells': kj.total_cells,
                'total_extracted': kj.total_extracted,
                'completed_at': kj.completed_at,
            })

        return Response({
            'bulk_job_id': bulk_job.id,
            'location': bulk_job.location,
            'status': bulk_job.status,
            'status_message': bulk_job.status_message,
            'total_extracted': bulk_job.total_extracted,
            'keywords': keyword_statuses,
            'created_at': bulk_job.created_at,
            'completed_at': bulk_job.completed_at,
        })


class BulkJobListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        jobs = BulkJob.objects.filter(
            user=request.user
        ).prefetch_related('keyword_jobs').order_by('-created_at')[:20]

        return Response([{
            'bulk_job_id': j.id,
            'location': j.location,
            'status': j.status,
            'keywords': [{
                'keyword_job_id': kj.id,
                'keyword': kj.keyword,
                'status': kj.status,
            } for kj in j.keyword_jobs.all()],
            'total_extracted': j.total_extracted,
            'created_at': j.created_at,
        } for j in jobs])


class KeywordResultsView(APIView):
    """Get results for one specific keyword."""
    permission_classes = [IsAuthenticated]

    def get(self, request, keyword_job_id):
        try:
            kj = KeywordJob.objects.select_related(
                'bulk_job'
            ).get(
                id=keyword_job_id,
                bulk_job__user=request.user
            )
        except KeywordJob.DoesNotExist:
            return Response({'error': 'Not found'}, status=404)

        places = kj.places.all().values(
            'name', 'category', 'street', 'city',
            'state', 'phone', 'website', 'rating',
            'review_count', 'maps_url', 'latitude', 'longitude'
        )
        return Response({
            'keyword': kj.keyword,
            'location': kj.bulk_job.location,
            'total': kj.total_extracted,
            'results': list(places),
        })


class ExportKeywordCSVView(APIView):
    """Download CSV for one specific keyword."""
    permission_classes = [IsAuthenticated]

    def get(self, request, keyword_job_id):
        try:
            kj = KeywordJob.objects.select_related(
                'bulk_job'
            ).get(
                id=keyword_job_id,
                bulk_job__user=request.user
            )
        except KeywordJob.DoesNotExist:
            return Response({'error': 'Not found'}, status=404)

        filename = (
            f"{kj.keyword}_{kj.bulk_job.location}"
            .replace(' ', '_') + '.csv'
        )
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = (
            f'attachment; filename="{filename}"'
        )

        fields = [
            'name', 'category', 'street', 'city', 'state',
            'phone', 'website', 'rating', 'review_count', 'maps_url'
        ]
        writer = csv.DictWriter(
            response, fieldnames=fields, extrasaction='ignore'
        )
        writer.writeheader()

        for place in kj.places.all():
            writer.writerow({
                f: getattr(place, f, '') for f in fields
            })

        return response


class BulkJobDeleteView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, bulk_job_id):
        try:
            bulk_job = BulkJob.objects.get(id=bulk_job_id, user=request.user)
            bulk_job.delete()
            return Response({'status': 'deleted'})
        except BulkJob.DoesNotExist:
            return Response({'error': 'Not found'}, status=404)
