from .jobs import JobCog

async def setup(bot):
    await bot.add_cog(JobCog(bot))
