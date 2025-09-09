from .jobs import JobCog

async def setup(bot):
    await bot.add_cog(JobCog(bot))

    #도적스킬
    from .skills.thief.steal import Steal
    await bot.add_cog(Steal(bot))
