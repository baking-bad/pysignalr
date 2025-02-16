using Microsoft.AspNetCore.SignalR;

namespace AspNetAuthExample.Hubs;

// Define a SignalR Hub for weather updates
public class WeatherHub : Hub
{
    // Method to send a message to all connected clients
    public async Task SendMessage(string user, string message)
    {
        await Clients.All.SendAsync("ReceiveMessage", user, message);
    }

    // Method to send a message to a specific group
    public async Task SendMessageToGroup(string groupName, string user, string message)
    {
        await Clients.Group(groupName).SendAsync("ReceiveMessage", user, message);
    }

    // Method to add a client to a group
    public async Task AddToGroup(string groupName)
    {
        await Groups.AddToGroupAsync(Context.ConnectionId, groupName);
        await Clients.Group(groupName).SendAsync("ReceiveMessage", "System", $"{Context.ConnectionId} has joined the group {groupName}.");
    }

    // Method to remove a client from a group
    public async Task RemoveFromGroup(string groupName)
    {
        await Groups.RemoveFromGroupAsync(Context.ConnectionId, groupName);
        await Clients.Group(groupName).SendAsync("ReceiveMessage", "System", $"{Context.ConnectionId} has left the group {groupName}.");
    }

    // Method to send the weather forecast to all clients
    public async Task SendWeatherForecast(string forecast)
    {
        await Clients.All.SendAsync("ReceiveWeatherForecast", forecast);
    }

    /// <summary>
    /// Trigger client result by invokeAsync method
    /// </summary>
    /// <param name="user"></param>
    /// <param name="message"></param>
    public async Task TriggerResultRequired(string user, string message)
    {
        var response = await Clients.Client(Context.ConnectionId).InvokeAsync<string>("ResultRequired", "Reply this message", CancellationToken.None);
        if (response == "Reply message")
            await Clients.Client(Context.ConnectionId).SendAsync("SuccessReceivedMessage", user, message);
    }
}
