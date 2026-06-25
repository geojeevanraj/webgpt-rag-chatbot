import asyncio
from sqlalchemy import select
from app.core.database import async_session_factory
from app.models.database import ScrapeJob, QuestionSuggestion

async def insert_mock():
    print("Connecting to database...")
    async with async_session_factory() as session:
        # Find the first completed job
        stmt = select(ScrapeJob).where(ScrapeJob.status == "completed").limit(1)
        res = await session.execute(stmt)
        job = res.scalar_one_or_none()
        
        if not job:
            print("No completed scrape job found in database. Please scrape a website first!")
            return
            
        print(f"Found completed job: {job.domain} (ID: {job.id})")
        
        # Check if suggestions already exist
        sugg_stmt = select(QuestionSuggestion).where(QuestionSuggestion.job_id == job.id)
        sugg_res = await session.execute(sugg_stmt)
        existing = sugg_res.scalars().all()
        
        if existing:
            print(f"Suggestions already exist for this job: {[s.question for s in existing]}")
            return
            
        # Create 4 mock suggestions
        mock_questions = [
            f"What is the main purpose of {job.domain}?",
            f"How do I get started with the features of {job.domain}?",
            f"What are the advanced use cases discussed in {job.domain}?",
            f"Give a summary of the technical design in {job.domain}."
        ]
        
        for q in mock_questions:
            sugg = QuestionSuggestion(
                job_id=job.id,
                question=q
            )
            session.add(sugg)
            
        await session.commit()
        print(f"Successfully inserted {len(mock_questions)} mock suggestions for job {job.id}!")

if __name__ == "__main__":
    asyncio.run(insert_mock())
