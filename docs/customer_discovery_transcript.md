# Customer Discovery Call — Transcript (Round 1 mock interview)

> Saved verbatim as the primary source for requirements. `ARIZE_EVAL_CONTEXT.md` and
> `docs/BUILD_LOG.md` both summarize/derive from this; when in doubt, this file is
> the ground truth. Speaker note from the user: the call has three real speakers
> (Nick Luzio, An Nguyen, Sofia Jakovcevic); any other raw labels are transcription
> splits, not additional people. In this transcript, "Sofia Jakovcevic" is the
> candidate (Sharan) driving discovery — likely a diarization/label mixup, not a
> fourth participant.

## Meeting Info
- Attendees: Sharan Arora, Schedule

## Summary

### Flow Summary
Round-one mock customer interview for an Arize FDE role: discovery on building an
eval framework around a travel-itinerary agent. Next round is a solution design
and demo using a provided repo.

### Interview Format
- Round 1 mock customer discovery; interviewers played head of product, PM, and
  VP of eng for a travel agency
- Round 2 will be end-to-end solution design plus demo of the eval framework

### Customer Case: Itinerary Agent + Evals
- Public-facing agent recommending itineraries; phase 2 later adds bookings;
  target prod in 2-3 months
- Top failure modes: correctness and groundedness (real, available flights/hotels);
  secondary: staying on-topic, tone
- Today evals are anecdotal via spreadsheets; want continuous evals, threshold
  alerts, and auto-drafted PRs for fixes
  - Target ~85-95% correctness; team wants ASAP alerts on threshold breaches
- Framework must be modular across future agents; scale concern is cost control,
  not throughput; availability/latency critical

### Logistics
- Sample agent repo shared in Zoom chat; focus is the eval framework, not the
  agent build
- Logs not currently stored anywhere; design should propose where they live

### Next Steps
- (An Nguyen) Follow up with current conversion rate baseline for the agent
- (Sofia Jakovcevic) Pull sample agent repo from Zoom chat
- (Sofia Jakovcevic) Design eval framework (deterministic checks + LLM-as-judge)
  and prepare solution presentation and demo for round 2

### Decisions Made
- Round 2 will cover solution design and demo; no solutioning required on this call
- Scope is the eval framework around the provided agent, not the agent build itself

## Transcript

[01:48] An Nguyen: Hey, how's it going?
[01:52] Sofia Jakovcevic: Hey, doing well. How are you?
[01:54] An Nguyen: Good.
[02:12] Sofia Jakovcevic: Busy week?
[02:13] An Nguyen: A little bit, yeah. What about you?
[02:18] Sofia Jakovcevic: Pretty hectic. Just a couple—well, several—different deliverables. I'm on three projects right now, and they all seem to want a lot of things at the same time, so it's been fun.
[02:30] An Nguyen: That's about right. Did you—are you—did you end up moving? Is that complete?
[02:36] Sofia Jakovcevic: Yes, yes. I'm in New York.
[02:37] An Nguyen: Okay, congrats. How did that go?
[02:41] Sofia Jakovcevic: It has been good so far. I like waking up in the morning and seeing the city, so I enjoy that.
[02:46] An Nguyen: Nice. I hope it wasn't too, too hectic moving.
[02:50] Sofia Jakovcevic: No, not at all.
[02:51] An Nguyen: Hey, Nick.
[02:52] Nick Luzio: Hey, all. How's it going?
[02:54] An Nguyen: Good. How are you?
[02:55] Nick Luzio: Pretty good.
[03:00] Nick Luzio: We're waiting on Sophia today.
[03:03] An Nguyen: Yeah.
[03:07] Nick Luzio: Got issues.
[03:10] An Nguyen: Hello, everyone. Apologies for coming in a couple minutes late.
[03:13] Nick Luzio: No problem. Cool. Probably worth doing some intros, and then we can jump in from there.
[03:25] Sofia Jakovcevic: Sounds good.
[03:26] Nick Luzio: Great. And you guys have already met, I assume?
[03:28] An Nguyen: Yeah.
[03:29] Nick Luzio: Cool. Well, I can kick off. I'm Nick.
[03:32] Nick Luzio: I lead our solutions team for the Americas. It's kind of our customer success group and our far deployed engineering division as well.
[03:43] Nick Luzio: I'm based in Jersey, so I got a New York office. Great to meet you.
[03:50] Nick Luzio: Sophia, if you want to do a quick intro.
[03:53] An Nguyen: Yep. Hello, I'm Sophia. I'm one of the forward deployed engineers here at Arise, currently based in Chicago, and it's also lovely to meet you.
[04:03] Sofia Jakovcevic: Likewise.
[04:05] Nick Luzio: Cool. Yeah, probably start with a quick intro from you, and then we'll go from there.
[04:13] Sofia Jakovcevic: Yeah, yeah, absolutely. I'm Sharan. Been with IBM for two-plus years as an engineer.
[04:20] Sofia Jakovcevic: Been on multiple different projects. My background is in working with GraphRAG systems, building retrieval and telemetry loggers, as well as building analytical frameworks for clients at the DoD, many of them.
[04:40] Sofia Jakovcevic: And yeah, just excited to be here.
[04:44] Nick Luzio: Great. Thanks for the background there. Cool.
[04:48] Nick Luzio: So the way that we run these interviews, we'll kind of play like a mock customer. This is round one for you, right?
[04:55] Sofia Jakovcevic: Yeah.
[04:56] Nick Luzio: Yeah. So we are—we'll play a mock customer. We're kind of a—think of us as a travel agency.
[05:05] Nick Luzio: We'll each play a different role on the team. I'll kind of be our—I'll be our head of product for this.
[05:11] Nick Luzio: And do you want to take product manager?
[05:13] An Nguyen: Yeah.
[05:14] Nick Luzio: All right. Great. And then, Sophia, you'll be whatever's left over, which is the VP of engineering today.
[05:22] Nick Luzio: So each of us kind of have different ideas about what we're looking for from the engagement. But overall, we've built an application and are looking to get an eval pipeline or get eval loop built around it.
[05:38] Nick Luzio: From your perspective, I would treat this just like a kind of a customer engagement. So ask discovery questions.
[05:45] Nick Luzio: Feel free to kind of take it in any direction you want to for this one. And then this will dictate kind of the solution that you build, and then you'll present that in the next round.
[05:56] Sofia Jakovcevic: Okay.
[05:57] Nick Luzio: Cool. Any questions on that?
[06:00] Sofia Jakovcevic: Yeah. Before we begin, is it all right if I'm able to type up notes on the side?
[06:06] Nick Luzio: Yeah, for sure. You can use notes. You can record if you want to.
[06:09] Nick Luzio: Anything you want to do is fine with me.
[06:11] Sofia Jakovcevic: Okay. Sounds good. Thank you.
[06:13] Sofia Jakovcevic: I appreciate that.
[06:13] Nick Luzio: Cool.
[06:16] Nick Luzio: All right. If no other questions, we'll kind of start the scene.
[06:20] Nick Luzio: We'll start playing the role, and feel free to kick us off however you want to.
[06:35] Sofia Jakovcevic: Oh, sorry. Just to clarify, so for this one, you'd want me to start off just in general, or is this an introduction first, and then I can start asking questions from there?
[06:50] Nick Luzio: Yeah. If it'd be helpful, we can give you an overview of what we've built. Just whatever would be most helpful, let me know, and then we can go from there.
[07:00] Sofia Jakovcevic: Okay. Yeah. Let's get started from there.
[07:04] Sofia Jakovcevic: Maybe let's spend some time understanding a little bit about your business and what exactly it is that you're looking to get out of it today, what exactly your business objective is.
[07:16] Nick Luzio: Okay. Yeah. Hey, anyone want to take it?
[07:19] An Nguyen: Yeah. I can pass that. Yeah.
[07:21] An Nguyen: So I'll start at a high level. So at our company, there has been a push to just roll out agents across the org, internal ones, external-facing ones.
[07:36] An Nguyen: So this is going to be a part of a broader AI push. My team specifically, we are working on the agent that is going to be on our public-facing website.
[07:50] An Nguyen: So the goal of this agent is that for prospective customers, they can come, they can talk with it, interact, and get a recommendation for an itinerary based off kind of where they want to go, when they want to go, what they want to do. I think for the first pass of getting this into production, that's all we're trying to do.
[08:12] An Nguyen: Down the line, in the future, we would like to be able to have them or we would like for them to be able to use this agent in order to actually book their flights, their hotels, their actual travel. But for this first pass, we just want it to be really solid with suggesting good itineraries for prospective customers.
[08:36] Sofia Jakovcevic: Got it. Got it. Thank you for that.
[08:38] Sofia Jakovcevic: So just to clarify, the first pass that you're looking to roll out this agent for is to be able to create an itinerary, a good one. And then the second pass would be to be able to create actual bookings and take those user conversations and convert them into finalized bookings.
[08:57] Sofia Jakovcevic: Is that correct?
[08:57] An Nguyen: Yes, that's correct. I would say for this first round of taking it to production, I would not necessarily worry about making the actual bookings. That's just something to keep in mind.
[09:09] An Nguyen: Right now, nothing's in production yet, and I just want that first release to be really good at itineraries. And so far, my team and I, we've just been kind of chatting with it intermittently and just kind of jotting down notes of how good the responses are.
[09:26] An Nguyen: It's a little chaotic, and we're just kind of storing things in spreadsheets, so there's not really a quantifiable way to measure how well it's performing. So that's really the area that we're looking for help on.
[09:40] Sofia Jakovcevic: Got it. Got it. That's actually a really good point.
[09:43] Sofia Jakovcevic: Maybe something I'd want to get a better understanding of. You mentioned the team jots down notes.
[09:50] Sofia Jakovcevic: Currently, there's no real sophisticated method to evaluating the quality of the responses. So it's how I would describe it as anecdotal.
[10:02] Sofia Jakovcevic: Do you mind maybe sharing more information on what a good versus a bad response in your experience has looked like so far?
[10:10] An Nguyen: Yeah. So I think a few themes that have popped up. The first one for me is going to be just general correctness, right?
[10:21] An Nguyen: So if I, as a user, am asking for an itinerary for Miami for a specific set of dates, I want the itinerary to reflect that and not Maui for a date a month off of what I requested, right? So the first thing is going to be that correctness.
[10:41] An Nguyen: And then the second thing that we've been seeing that's going to be just a major issue if it happens in production is going to be groundedness. So when it crafts itineraries, I need the suggested flights and hotels.
[10:57] An Nguyen: I need them to be real, and I need for those to actually be available on the dates that they're suggesting, right? So if it's suggesting for a customer to book flight ABC, and that's not an actual flight, I'm sure you can imagine that's going to be a big headache for us.
[11:15] Sofia Jakovcevic: Got it. So again, just to clarify, one is general correctness, which is what you're looking for. So maybe the parameters of the request, if you want to go from point A to point B, it shouldn't give you any suggestions related to point C that isn't relevant to your request.
[11:32] Sofia Jakovcevic: And then the other one would be well-roundedness. So the suggested, for example, flights, hotels, they must be real and must be available.
[11:41] Sofia Jakovcevic: So it must be accurate, and it shouldn't be hallucinating any sort of false responses that just may not exist.
[11:47] An Nguyen: Correct.
[11:48] Sofia Jakovcevic: Would that be correct?
[11:49] An Nguyen: Yes.
[11:49] Sofia Jakovcevic: Okay. Got it. Got it.
[11:53] Sofia Jakovcevic: And between these two issues so far, what would you flag as maybe what failures would you say are the most important ones?
[12:03] An Nguyen: I would say those.
[12:04] Sofia Jakovcevic: You have that to your left.
[12:05] An Nguyen: Just between those two. Yeah. Actually, they're both equally important for me, right?
[12:11] An Nguyen: If either of them I have a series of other kind of secondary metrics that I'm tracking, but those two have to be working really well for me to be comfortable with this operating in production.
[12:25] Sofia Jakovcevic: Got it. And would you say there are any other issues that come to mind that might be potential challenges for this agent?
[12:35] An Nguyen: Yeah. I would say tone, generally speaking, one that we want to keep in mind, right? It's public-facing.
[12:43] An Nguyen: It's representing our company. We want it to be professional.
[12:47] An Nguyen: Another thing would be just making sure that the conversation remains just relevant to travel and itinerary recommendations. We don't want the general public abusing it just for tokens to go solve math problems or what have you.
[13:05] An Nguyen: So I would say, yeah, those are the other things that we want to make sure it's performing relatively well on.
[13:11] Sofia Jakovcevic: Got it. And maybe circling back to the previous question I had about ranking the failures, these other things to keep in mind, the tone, ensuring publicism, maxing out tokens that aren't relevant to the conversation either.
[13:30] Sofia Jakovcevic: Would you say that they fall below in terms of importance for you when you're looking for this agent to perform well, or would you now tier them differently?
[13:39] An Nguyen: I would say, yeah, tone is slightly less important for me. I would say it needs to be correct. I would say probably the one where we want it to stay relevant within bounds, that's also up there, right?
[13:52] An Nguyen: Just we don't want our tokens to get used for other things.
[13:59] Sofia Jakovcevic: Got it. Got it. Okay.
[14:00] Sofia Jakovcevic: That's very helpful. Thank you for that.
[14:03] Sofia Jakovcevic: Maybe let's delve into some of the challenges in terms of how we're catching them so far. So you've mentioned that you have you're going through log notes, and this agent hasn't gone into production today.
[14:21] Sofia Jakovcevic: So what's your current process to being able to identify maybe what the ground truth is or label data? How are you currently evaluating it?
[14:33] An Nguyen: Yeah. So that's all human-based right now. So yeah, my team, we're just kind of talking with it and getting responses.
[14:42] An Nguyen: And then we're basically just slowly curating a golden data set, right, of just what is a good response versus not.
[14:55] Sofia Jakovcevic: Okay.
[14:58] Sofia Jakovcevic: That makes sense. So it's just purely human.
[15:02] Sofia Jakovcevic: Okay. And when you're looking to be able to identify these issues, how important is speed of being alerted that the agent may have created certain responses that are what you would classify as bad or poor ones based on the issues that you've noted so far?
[15:25] An Nguyen: Yeah. I would say ASAP, to be honest. So yeah, we just love to have, obviously, once in production, right, just a continuous evaluation happening on it.
[15:34] An Nguyen: And then whenever there's the percentage of sort of poor outcomes, depending on the metric, that hits below a certain threshold or when it performs well, sorry.
[15:50] An Nguyen: When that falls below a certain threshold, then I would want my team and Sophia's team to be notified so we can take a look at it ASAP just so that those issues don't linger in production for too long.
[16:01] Sofia Jakovcevic: Okay. That makes sense. You actually mentioned something I was interested in asking about the metrics falling below certain thresholds.
[16:10] Sofia Jakovcevic: Could you maybe shed some light on what those metrics are?
[16:12] An Nguyen: Yeah. Yeah. I mean, it's just really a percentage, right?
[16:16] An Nguyen: So let's take the general correctness one, for example, right? So you think of a conversation that a user's having with the agent.
[16:26] An Nguyen: Ultimately, the outcome is either correct or incorrect. So over time, I would want that percentage to be relatively high.
[16:35] An Nguyen: I think for a first pass, maybe between 85, 90 percent would be possible. Would obviously love your suggestions and kind of give us your recommendations on what you think that should be.
[16:46] An Nguyen: But I'm thinking for something for those high-priority metrics, I want it to be correct and grounded more often than not.
[16:56] Sofia Jakovcevic: Got it. Got it. Okay.
[16:59] Sofia Jakovcevic: I would say I definitely have some ideas in mind, but I don't want to necessarily prescribe a solution quite just yet. I think we can spend more time learning a bit more.
[17:10] Sofia Jakovcevic: Okay. So generally looking around that 85 to 95 percent of correctness, which would be important.
[17:19] Sofia Jakovcevic: When you're trying to push this into production, do you have a timeline in mind by when you're looking to push this out and ensure that the agent quality remains as how you would hope it would be?
[17:37] Sofia Jakovcevic: Do you have a timeline in mind?
[17:38] An Nguyen: Yeah. I would like to get this into production, honestly, in the next two to three months just so that we can start rolling it out sooner rather than later.
[17:49] Sofia Jakovcevic: Okay.
[17:54] Sofia Jakovcevic: And what are you thinking from a traffic perspective? How many customers or visitors do you envision using this agent on a daily basis?
[18:06] An Nguyen: I think probably to start in the realm of hundreds, maybe low thousands of conversations a day. That's what I imagine it will be. But I think that once we roll it out in the first few weeks, we'll get a stronger sense.
[18:22] Nick Luzio: It's really important that we can scale to the millions when we need to. So we want to keep scaling in the back of our mind.
[18:33] Sofia Jakovcevic: Got it.
[18:37] Sofia Jakovcevic: Thank you for that. That's helpful.
[18:40] Sofia Jakovcevic: And beyond just the scaling and handling the incoming traffic, are there any other constraints that come to mind? Maybe considering cost, budget limits, are those factors that you would view as something important?
[18:59] Sofia Jakovcevic: Yes, absolutely. We want to make sure that we can monitor our costs at every step of the way, especially if we're going to be adding some sort of evaluations, being able to monitor how much we're spending on evaluating and how much we're actually spending on agents is going to be very important for our team.
[19:21] Sofia Jakovcevic: Do you have a dedicated team in mind who would be doing the evaluation of the responses, or would it vary based on maybe team goals and priorities?
[19:33] Sofia Jakovcevic: Ideally, we'd like to onboard many team members to at least have the knowledge of how the evaluators are operating, being able to update them as need be. Maybe later down the line, we could talk about formulating a guideline for how they should be doing that.
[20:00] Sofia Jakovcevic: Got it. Okay. That is helpful.
[20:02] Sofia Jakovcevic: Thank you for that. So right now, you're just looking to onboard many team members, evaluators operating, the guidelines.
[20:12] Sofia Jakovcevic: Sorry, just to clarify how the evaluators are doing, but in terms of formulating the guidelines, maybe that's something that's for a future day, not right now.
[20:24] Sofia Jakovcevic: Guidelines for how we want to evaluate our agents that we'd like to formulate sooner about how our users or how our team members are going to be working with those evals and the process for updating them and optimizing them. That's something that can be discussed later.
[20:41] Sofia Jakovcevic: Okay. Got it. Got it.
[20:43] Sofia Jakovcevic: Thank you for that. That's very helpful.
[20:46] Sofia Jakovcevic: Okay. So maybe just circling back a little bit to the bigger picture in terms of the goal of rolling out this agent that's able to help answer user queries in terms of creating an itinerary, how would you say well, what would you say success looks like in the upcoming two to three months once this has been rolled into production?
[21:13] An Nguyen: Yeah. Really, I can speak to the business success metrics that we're tracking here. So it's a couple of things.
[21:20] An Nguyen: So one, we are hoping that since this will be more self-serve, I want to increase the conversion rate of and that's just going to be the people who actually end up booking with us over the people who just begin to go to our website and have a conversation with the agent. So that'll be the first one.
[21:41] An Nguyen: And then the second one is going to be reducing the number of requests to speak with a live support agent or customer support person, right? Because as you can imagine, that's rather costly for us.
[21:59] An Nguyen: So if this agent can just convert people just via the chat interface as much as possible, I would consider that a win.
[22:11] Sofia Jakovcevic: Got it. So right now, in terms of business metrics, you're seeking increased conversion rate as well as decreasing number of requests to speak with live support agents or live support.
[22:21] An Nguyen: Yeah.
[22:22] Sofia Jakovcevic: Got it. Regarding the increased conversion rate, do you have a specific threshold in mind, or is this just a general we'd like to see an improvement?
[22:32] An Nguyen: Generally, we'd like to see an improvement. I still need to pull exact goals from leadership, but for now, it's just general improvement.
[22:41] Sofia Jakovcevic: Okay. Do you think you'd be able to provide what the current conversion rate is? Is that something you're tracking?
[22:49] An Nguyen: I can pick it up and follow back up with you on it. Yeah. I think just kind of that's the high level, right?
[22:56] An Nguyen: So if we just focus down to, I think, as long as we have a good way to track those metrics for the agent specifically, I believe that that will help those business metrics. So that's fine for me and my team to take on that hypothesis and deal with it.
[23:14] An Nguyen: I think what I'm just looking for more is more from the technical perspective, having a way to actually just measure how well the agent is doing.
[23:24] Sofia Jakovcevic: Got it. Got it. Okay.
[23:26] Sofia Jakovcevic: So then maybe we can delve into the feedback component as well since you brought up the agent. One thing I'm curious about is, given the different challenges or issues that the agent should ideally avoid to craft a really good response, on the responses that are bad, when an evaluation does occur for this bad response, what do you envision should occur?
[23:54] An Nguyen: So when an evaluation just shows that a response is bad, what do I think should happen? Is that right? Yeah.
[24:02] Sofia Jakovcevic: Yeah.
[24:02] An Nguyen: So I would expect sorry, expect a couple of things. The first one would be kind of going back to that threshold that we mentioned, right? If in production, the agent is starting to consistently misbehave, I would want my team and Sophia's team to be alerted and be aware of that so that we can kind of go in there and dig in and figure out what's going on.
[24:26] An Nguyen: The second piece of that is going to be more that kind of automated feedback loop piece that I've been kind of hearing about in the industry. Once if we get a pattern of bad results on the evals, would love it if there could be PRs, draft PRs put up.
[24:49] An Nguyen: I would still want someone from Sophia's team to take a look at it and review it themselves, but would love to get to a point where we can have suggested fixes or even improvements for our agent just generated for us based off how those evals are doing.
[25:09] Sofia Jakovcevic: Got it. So just breaking it down into two parts, as you said. So one would be alerts based on threshold violations in production.
[25:20] Sofia Jakovcevic: You would be updated, as well as Sophia would be updated ASAP. And then the second component is the automated feedback loop, identifying any pattern trends, putting up draft PRs, as well as suggesting fixes or improvements for the agent.
[25:35] An Nguyen: Yep.
[25:37] Sofia Jakovcevic: Okay.
[25:42] Sofia Jakovcevic: Cool. And then when you are looking at this evaluation loop, how often should the evaluation loop be running?
[25:56] An Nguyen: I think to start so for the evals themselves, I want those to be running continuously. I don't really see the reason why they shouldn't be. I think that's the best way that my team can get alerted if something is going awry in production.
[26:16] Sofia Jakovcevic: Okay.
[26:19] Sofia Jakovcevic: Got it. And so maybe just walking briefly through the loop, user ends up using the agent.
[26:31] Sofia Jakovcevic: The agent crafts a response. The response is now documented, and the response could be good.
[26:38] Sofia Jakovcevic: But assuming the response is bad, we want to be alerted, identified, be capturing patterns, as well as suggesting fixes. Given some of the business outcomes that you have mentioned as well, maybe delving into the stakeholders and visibility, what type of business decision would you be making based off of capturing and evaluating these responses?
[27:07] Sofia Jakovcevic: Or is there a connection that you can draw between the evaluation response to any sort of business decisions that need to be made?
[27:17] An Nguyen: Yeah. So for this agent specifically, right, I get a certain budget to do this and to spend on tokens, right? So I think if it performs well and we have a way of continuously improving it, I think the main decision there is we can keep on having it.
[27:37] An Nguyen: And that's assuming that we get improvements on those business metrics we were talking about. So conversion rate, reducing support hours.
[27:47] An Nguyen: So I think those would be the biggest thing. Going a bit further out, though, I mentioned earlier in this call that this is just going to be one of many agents that we're rolling out at the org.
[28:01] An Nguyen: So obviously, selfishly, I want this one to do really well. But the framework or this loop that we set up, it does need to be relatively easy to repeat it across different agents that teams will be rolling out down the line.
[28:18] An Nguyen: Obviously, the exact evals and metrics are going to differ based on the use case, but the general structure of how we think about evaluating and improving on agents, that should carry over.
[28:34] Sofia Jakovcevic: Got it. Got it. So how I would qualify that is my understanding is essentially we're building it for your specific agent.
[28:46] Sofia Jakovcevic: However, it needs to be the eval loop needs to be modular enough so that it can be scaled across other agents within the company as well. Okay.
[28:58] Sofia Jakovcevic: Got it. Got it.
[29:01] Sofia Jakovcevic: Let's see.
[29:07] Sofia Jakovcevic: I think in terms so maybe I can spend some time just overall summarizing my understanding of the case so far and just confirm all the different details. So right now, we're trying to push out an agent in two phases.
[29:27] Sofia Jakovcevic: Currently, we're focused on phase one. Phase one being being able to help users create an itinerary.
[29:35] Sofia Jakovcevic: And we're looking to roll this out into production over the course of the next two to three months. We have an idea of important elements of the agent's responses, good and bad.
[29:49] Sofia Jakovcevic: We would want the agent to be generally correct, adhere to different parameters of request, being able to suggest accurate information such as flights, hotels must be real and available. At the moment, however, there isn't a concrete systematic way that can evaluate the responses on scale.
[30:09] Sofia Jakovcevic: It's fairly anecdotal, but we are capturing all the different responses that are taking place. So it's all just human evaluation.
[30:20] Sofia Jakovcevic: There's no sort of systematic, deterministic, or judge, you could call it, to understand and be able to evaluate those responses, whether they're good or not. In terms of those failures, most of them are fairly equally important.
[30:39] Sofia Jakovcevic: Something like tone probably less so, but relevance, as well as some of the other ones, correctness and real data accuracy, those are up there. And then the response to agent quality dropping should be ASAP.
[30:58] Sofia Jakovcevic: If there are any threshold violations, you would want to be alerted. The appropriate team would want to be alerted because this is something we're trying to scale.
[31:06] Sofia Jakovcevic: In the early few weeks, might be a couple hundred to a thousand different users, but ideally, the solution should be scalable across millions. And then in terms of general correctness, as an example for one of our business metrics or excuse me, not business metrics, but the agent quality metric itself should remain between 85 to 95 percent.
[31:35] Sofia Jakovcevic: And then lastly, in terms of stakeholders, would want to onboard many team members. If this evaluation loop shows that it's doing really well, then, of course, the budget can be scaled up.
[31:51] Sofia Jakovcevic: And the eval loop, again, needs to be modular and work across multiple agents. And then just being alerted, have that automated feedback loop.
[32:03] Sofia Jakovcevic: This would be the most important element of that feedback cycle is identifying patterns, drafting any PRs, and making suggested improvements. Do you feel with everything I've described so far, I've captured the case well?
[32:21] An Nguyen: I think so for me or about Sophia and Nick, you too.
[32:26] Nick Luzio: Pretty good from my side. I think from my perspective, just looking at the higher level of things, right, like some of the other use cases we have, I want to make sure the or whatever we implement here is easily generalizable to whatever other agents we use and whatever other use cases we bring on board. So I'm looking for more of a framework than a single solve for this agent.
[32:52] Nick Luzio: But I think in general, yeah, we got the right approach. Yeah, I second that.
[32:59] Nick Luzio: Scale is really important for us because we want to be able to grow this
[33:02] Sofia Jakovcevic: and expand not only horizontally, but also vertically. So other teams can also pick up the same framework that we've laid out here. Cost is also front of mind and reliability as well.
[33:13] Sofia Jakovcevic: It's very important for us. We want to be able to ensure that our users can rely on this product.
[33:24] Sofia Jakovcevic: Now, when you say reliability, just to clarify, when you say reliability, you're talking about the quality of the agent or the availability of the agent? As in, is the tool even available to use, or maybe it's just not functioning at all?
[33:40] Sofia Jakovcevic: Both. And quality is important, but I really want to focus on the availability and making sure that we keep the agent up, that there isn't any downtime for our users. Nothing's worse than talking with a chatbot and waiting five minutes for a response.
[33:59] Sofia Jakovcevic: Yeah. Speed of response. Okay.
[34:10] Sofia Jakovcevic: Got it. Okay.
[34:12] Sofia Jakovcevic: Okay. Thank you.
[34:13] Sofia Jakovcevic: That is really helpful. So in terms of next steps, I'm thinking from the evaluation standpoint, we would probably want to introduce a mixture of two different types of evaluation.
[34:35] Sofia Jakovcevic: One would be more what I would call deterministic, so ensuring simple information accuracy. If the user is asking for a particular itinerary, then we're adhering to those specific travel plans, as well as providing updated information.
[34:55] Sofia Jakovcevic: And then the other is when it comes to tone, more contextual information. If it's a mix and match that might be a little bit fuzzy and hard to judge by hard rules, then maybe leveraging some sort of LLM as a judge that might be able to help decipher.
[35:15] Sofia Jakovcevic: That's currently how I'm thinking about it. I'm certainly open to suggestions.
[35:21] Sofia Jakovcevic: One quick question I did have as I'm going through this for maybe the back half of this conversation is, now that we've spoken on the overall use case, what's most important, as well as some discussion about the stakeholders and how the information would be presented and how the eval loop can work or ideally should work and alert the right teams. Now, for this back half, are we thinking of maybe how we want to draft the solution itself?
[35:57] Sofia Jakovcevic: Or maybe we can start there in terms of just drafting the solution, maybe what I'm thinking step by step.
[36:08] Nick Luzio: Sorry. Is your question there can you repeat the question?
[36:13] Sofia Jakovcevic: Yeah. So maybe outside of the client-customer interaction for this part of the interview, because maybe I'm just slightly confused here, would you want me going over how I'm thinking about maybe high-level drafting the solution itself from a client conversation standpoint? Are you thinking about it differently?
[36:41] Sofia Jakovcevic: I just want to be clear on maybe how we want to walk the next set of steps with the time we have.
[36:47] Nick Luzio: I think if you're feeling good about questions asked and you feel like you've got a good path forward, so we definitely don't have to go through solution design on the call. Next call will be focused around that solution design, right? We'll go through the whole kind of the end-to-end presentation where you present how you design the solution, how it works, and then a demo of the actual solution.
[37:10] Nick Luzio: Don't feel like you have to fill the whole time, the whole hour by any means. We have the hour just in case we need it.
[37:16] Nick Luzio: But if you're feeling good and you feel like you got all the details you need to build, then no reason to fill the time if you don't need it.
[37:25] Sofia Jakovcevic: Yeah. So I have a so I have a few questions. It's a mixture of both.
[37:32] Sofia Jakovcevic: Maybe just for clarity, for the work week, in terms of the travel agent and building the feedback evaluation loop around it, is there anything I'm getting in terms of I'm being handed over an agent and then I'm building it around it?
[37:51] Sofia Jakovcevic: Because that was sort of the question I had about the process, but I don't think I ever really received too much clarity there. And I just want to make sure that I've not maybe overlooked anything.
[38:02] Nick Luzio: Yeah. We'll send you a repo that has an agent in there. We can probably send it over now.
[38:08] Nick Luzio: And if you have it handy, we can just drop it in the chat. Yeah.
[38:13] Nick Luzio: The goal is to not spend too much time on the actual agent. So we gave you the sample agent.
[38:18] Nick Luzio: Really, we're not super interested in the actual build of the agent, much more on the evaluation framework that goes around it.
[38:28] Sofia Jakovcevic: Okay. Got it. Got it.
[38:31] Sofia Jakovcevic: That is helpful to know.
[38:36] Sofia Jakovcevic: In terms of just probably one last-minute question I have about the current set of logs - it just occurred to me - the current set of logs, where are they being stored right now?
[38:53] Sofia Jakovcevic: Are they stored in some durable database?
[39:00] Sofia Jakovcevic: And is that important?
[39:01] Nick Luzio: The logs, current state or not, being stored anywhere, would be great to see where we should put them in the design.
[39:11] Sofia Jakovcevic: Okay.
[39:22] Sofia Jakovcevic: Okay.
[39:24] Sofia Jakovcevic: Okay. So I think that answers all my questions for now.
[39:30] Sofia Jakovcevic: Maybe I'll just do one last quick overview. Feeling pretty good about it.
[39:38] Sofia Jakovcevic: Want to roll out agent to prod, create user itinerary, first pass in about two to three months. Working towards evaluating the quality of the responses.
[39:50] Sofia Jakovcevic: Right now, one, the logs aren't stored anywhere. And two, the responses are evaluated manually.
[39:59] Sofia Jakovcevic: So there's no scalable systematic system or systematic methodology in place that would help you evaluate the responses, good or bad. And majority of the failures of the responses seem to be important.
[40:16] Sofia Jakovcevic: Tone's probably less important. The detection speed is extremely critical.
[40:21] Sofia Jakovcevic: So wanting to be alerted ASAP as soon as a response has fallen below threshold in terms of percentages. As an example, we had percentage of correctness within a given range of 85 to 95 percent.
[40:39] Sofia Jakovcevic: We're looking at a scale of millions potentially in the future, but for the time being, it would be in the hundreds to the low thousands, as well as needing to monitor costs and evaluation for the team. And then lastly, our evaluation loop should be running continuously.
[40:59] Sofia Jakovcevic: It should be an automated feedback loop, patterns, suggested fixes, as well as alerting of the thresholds. And then just some last-minute notes, of course.
[41:11] Sofia Jakovcevic: Logs currently are not stored anywhere. Speed of response is important.
[41:15] Sofia Jakovcevic: Quality and availability is critical of the actual agent itself. If users can't access the agent, then they're going to have a hard time using the product, scale, cost.
[41:27] Sofia Jakovcevic: And then, again, the ideal solution or the eval loop should be something that's more of a framework rather than limited and hard defined to one specific shelf or domain.
[41:43] Sofia Jakovcevic: Just a comment on the scale. Our concern with scale has mostly revolved around cost. As we scale cost from, let's say, thousands of requests to millions of requests, how can we counteract the cost for that?
[41:58] Sofia Jakovcevic: Less on whether or not we can scale and more so on how can we handle the cost that comes with that scale.
[42:05] Sofia Jakovcevic: Got it. So it's less the scale of the number of users, more of scale of the cost can ramp up really quickly.
[42:14] Sofia Jakovcevic: Yes. How can we counteract that?
[42:18] Sofia Jakovcevic: Okay. So thank you for that clarification. Appreciate it.
[42:28] Sofia Jakovcevic: Okay. I think that is all for my questions.
[42:34] Sofia Jakovcevic: Awesome.
[42:35] Nick Luzio: Thanks for taking some time today. If you have any just before we break, make sure to grab that repo from the Zoom chat so that you have it.
[42:45] Sofia Jakovcevic: Yes. Let me click on it just to make sure I have access to it. Awesome.
[42:52] Sofia Jakovcevic: I do. Thank you so much.
[42:54] An Nguyen: All right. Cool. Thanks for taking the time.
[42:55] An Nguyen: If you have questions, feel free in the meantime, feel free to send an email, and we can get questions answered from there. And then we look forward to next chat.
[43:08] Sofia Jakovcevic: Yeah. Looking forward to next week. Thank you, guys.
[43:10] Sofia Jakovcevic: I appreciate it.
[43:11] Sofia Jakovcevic: Thanks. Take care.
[43:12] Sofia Jakovcevic: Bye.
[43:13] Sofia Jakovcevic: Enjoy the rest of your week.
[43:15] Sofia Jakovcevic: You too.
[43:19] Sofia Jakovcevic: Ooh, that was a little.
